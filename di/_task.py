from __future__ import annotations

import functools
import typing
from collections import deque
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Deque,
    Dict,
    Generic,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Tuple,
    Union,
    cast,
)

from di._inspect import is_async_gen_callable, is_gen_callable
from di._state import ContainerState
from di.exceptions import IncompatibleDependencyError
from di.types.dependencies import DependantProtocol, DependencyParameter
from di.types.executor import Task as ExecutorTask
from di.types.providers import (
    AsyncGeneratorProvider,
    CallableProvider,
    CoroutineProvider,
    DependencyType,
    GeneratorProvider,
)


class ExecutionState(typing.NamedTuple):
    container_state: ContainerState
    results: Dict[DependantProtocol[Any], Any]
    dependency_counts: MutableMapping[DependantProtocol[Any], int]
    dependants: Mapping[DependantProtocol[Any], Iterable[Task[Any]]]


class Task(Generic[DependencyType]):
    __slots__ = ("dependant", "dependencies")

    def __init__(
        self,
        dependant: DependantProtocol[DependencyType],
        dependencies: List[DependencyParameter[Task[Any]]],
    ) -> None:
        self.dependant = dependant
        self.dependencies = dependencies

    def compute(
        self,
        state: ExecutionState,
    ) -> Union[
        Awaitable[Iterable[Optional[ExecutorTask]]], Iterable[Optional[ExecutorTask]]
    ]:
        raise NotImplementedError

    def gather_params(
        self, results: Dict[DependantProtocol[Any], Any]
    ) -> Tuple[List[Any], Dict[str, Any]]:
        positional: List[Any] = []
        keyword: Dict[str, Any] = {}
        for dep in self.dependencies:
            if dep.parameter is not None:
                if dep.parameter.kind is dep.parameter.kind.POSITIONAL_ONLY:
                    positional.append(results[dep.dependency.dependant])
                else:
                    keyword[dep.parameter.name] = results[dep.dependency.dependant]
        return positional, keyword

    def gather_new_tasks(
        self, state: ExecutionState
    ) -> Iterable[Optional[ExecutorTask]]:
        """Look amongst our dependants to see if any of them are now dependency free"""
        new_tasks: Deque[Optional[ExecutorTask]] = deque()
        for dependant in state.dependants[self.dependant]:
            count = state.dependency_counts[dependant.dependant]
            if count == 1:
                # this dependant has no further dependencies, so we can compute it now
                newtask = functools.partial(
                    dependant.compute,
                    state,
                )
                new_tasks.append(newtask)  # type: ignore[arg-type] # because of partial
                # pop it from dependency counts so that we can
                # tell when we've satisfied all dependencies below
                state.dependency_counts.pop(dependant.dependant)
            else:
                state.dependency_counts[dependant.dependant] = count - 1
        # also pop ourselves if we have no deps
        if state.dependency_counts.get(self.dependant, -1) == 0:
            state.dependency_counts.pop(self.dependant)
        if not state.dependency_counts:
            # all dependencies are taken care of, insert sentinel None value
            new_tasks.append(None)
        return new_tasks

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({repr(self.dependant)}, {repr(self.dependencies)})"


class AsyncTask(Task[DependencyType]):
    __slots__ = ()

    async def compute(
        self,
        state: ExecutionState,
    ) -> Iterable[Optional[ExecutorTask]]:
        args, kwargs = self.gather_params(state.results)

        assert self.dependant.call is not None
        call = self.dependant.call
        if is_async_gen_callable(call):
            stack = state.container_state.stacks[self.dependant.scope]
            if not isinstance(stack, AsyncExitStack):
                raise IncompatibleDependencyError(
                    f"The dependency {self.dependant} is an awaitable dependency"
                    f" and canot be used in the sync scope {self.dependant.scope}"
                )
            if TYPE_CHECKING:
                call = cast(AsyncGeneratorProvider[DependencyType], call)
            state.results[self.dependant] = await stack.enter_async_context(
                asynccontextmanager(call)(*args, **kwargs)
            )
        else:
            if TYPE_CHECKING:
                call = cast(CoroutineProvider[DependencyType], call)
            state.results[self.dependant] = await call(*args, **kwargs)

        return self.gather_new_tasks(state)


class SyncTask(Task[DependencyType]):
    __slots__ = ()

    def compute(
        self,
        state: ExecutionState,
    ) -> Iterable[Optional[ExecutorTask]]:

        args, kwargs = self.gather_params(state.results)

        assert self.dependant.call is not None
        call = self.dependant.call
        if is_gen_callable(self.dependant.call):
            if TYPE_CHECKING:
                call = cast(GeneratorProvider[DependencyType], call)
            stack = state.container_state.stacks[self.dependant.scope]
            state.results[self.dependant] = stack.enter_context(
                contextmanager(call)(*args, **kwargs)
            )
        else:
            if TYPE_CHECKING:
                call = cast(CallableProvider[DependencyType], call)
            state.results[self.dependant] = call(*args, **kwargs)

        return self.gather_new_tasks(state)
