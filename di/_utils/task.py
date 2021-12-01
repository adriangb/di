from __future__ import annotations

import threading
from contextlib import AsyncExitStack, ExitStack, asynccontextmanager, contextmanager
from typing import (
    Any,
    Deque,
    Dict,
    Generator,
    Iterable,
    Mapping,
    Optional,
    Tuple,
    TypeVar,
    Union,
    cast,
)

from graphlib import TopologicalSorter

from di._utils.inspect import is_async_gen_callable, is_gen_callable
from di.api.dependencies import DependantBase
from di.api.executor import AsyncTask as ExecutorAsyncTask
from di.api.executor import State
from di.api.executor import SyncTask as ExecutorSyncTask
from di.api.executor import Task as ExecutorTask
from di.api.providers import DependencyProvider
from di.api.scopes import Scope
from di.exceptions import IncompatibleDependencyError


class ExecutionState(State):
    __slots__ = (
        "stacks",
        "results",
        "toplogical_sorter",
        "lock",
    )

    def __init__(
        self,
        stacks: Mapping[Scope, Union[AsyncExitStack, ExitStack]],
        results: Dict[Union[AsyncTask, SyncTask], Any],
        toplogical_sorter: TopologicalSorter[Union[AsyncTask, SyncTask]],
    ):
        self.stacks = stacks
        self.results = results
        self.toplogical_sorter = toplogical_sorter
        self.lock = threading.Lock()


DependencyType = TypeVar("DependencyType")

TaskQueue = Deque[Optional[ExecutorTask]]


def gather_new_tasks(
    state: ExecutionState,
) -> Generator[Optional[ExecutorTask], None, None]:
    """Look amongst our dependants to see if any of them are now dependency free"""
    ts = state.toplogical_sorter
    res = state.results
    done = ts.done
    get_ready = ts.get_ready
    while ts.is_active():
        ready = get_ready()
        if not ready:
            break
        for t in ready:
            if t in res:
                done(t)
            else:
                yield t
    if not ts.is_active():
        yield None


class Task:
    __slots__ = (
        "dependant",
        "call",
        "positional_parameters",
        "keyword_parameters",
        "scope",
    )
    call: DependencyProvider
    scope: Scope

    def __init__(
        self,
        dependant: DependantBase[Any],
        positional_parameters: Iterable[Union[AsyncTask, SyncTask]],
        keyword_parameters: Iterable[Tuple[str, Union[AsyncTask, SyncTask]]],
    ) -> None:
        self.dependant = dependant
        self.scope = self.dependant.scope
        assert dependant.call is not None
        self.call = dependant.call
        self.positional_parameters = positional_parameters
        self.keyword_parameters = keyword_parameters

    def gather_params(
        self, results: Dict[Union[AsyncTask, SyncTask], Any]
    ) -> Tuple[Iterable[Any], Mapping[str, Any]]:
        """Gather all parameters (aka *args and **kwargs) needed for computation"""
        return (
            (results[t] for t in self.positional_parameters),
            {k: results[t] for k, t in self.keyword_parameters},
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({repr(self.dependant)})"


class AsyncTask(Task, ExecutorAsyncTask):
    __slots__ = ("is_generator",)

    def __init__(
        self,
        dependant: DependantBase[Any],
        positional_parameters: Iterable[Union[AsyncTask, SyncTask]],
        keyword_parameters: Iterable[Tuple[str, Union[AsyncTask, SyncTask]]],
    ) -> None:
        super().__init__(dependant, positional_parameters, keyword_parameters)
        self.is_generator = is_async_gen_callable(self.call)
        if self.is_generator:
            self.call = asynccontextmanager(self.call)  # type: ignore[arg-type]

    async def compute(
        self,
        state: State,
    ) -> Iterable[Optional[ExecutorTask]]:
        state = cast(ExecutionState, state)
        args, kwargs = self.gather_params(state.results)

        if self.is_generator:
            try:
                enter = state.stacks[self.scope].enter_async_context  # type: ignore[union-attr]
            except AttributeError:
                raise IncompatibleDependencyError(
                    f"The dependency {self.dependant} is an awaitable dependency"
                    f" and canot be used in the sync scope {self.dependant.scope}"
                )
            state.results[self] = await enter(
                self.call(*args, **kwargs)  # type: ignore[arg-type]
            )
        else:
            state.results[self] = await self.call(*args, **kwargs)  # type: ignore[misc]
        state.toplogical_sorter.done(self)
        return gather_new_tasks(state)


class SyncTask(Task, ExecutorSyncTask):
    __slots__ = ("is_generator",)

    def __init__(
        self,
        dependant: DependantBase[Any],
        positional_parameters: Iterable[Union[AsyncTask, SyncTask]],
        keyword_parameters: Iterable[Tuple[str, Union[AsyncTask, SyncTask]]],
    ) -> None:
        super().__init__(dependant, positional_parameters, keyword_parameters)
        self.is_generator = is_gen_callable(self.call)
        if self.is_generator:
            self.call = contextmanager(self.call)  # type: ignore[arg-type]

    def compute(
        self,
        state: State,
    ) -> Iterable[Optional[ExecutorTask]]:
        state = cast(ExecutionState, state)
        args, kwargs = self.gather_params(state.results)

        if self.is_generator:
            state.results[self] = state.stacks[self.scope].enter_context(
                self.call(*args, **kwargs)  # type: ignore[arg-type]
            )
        else:
            state.results[self] = self.call(*args, **kwargs)
        state.toplogical_sorter.done(self)
        return gather_new_tasks(state)
