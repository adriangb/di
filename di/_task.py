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
from di.types.dependencies import DependantBase, DependencyParameter
from di.types.executor import AsyncTaskInfo, SyncTaskInfo, TaskInfo
from di.types.providers import (
    AsyncGeneratorProvider,
    CallableProvider,
    CoroutineProvider,
    DependencyType,
    GeneratorProvider,
)


class ExecutionState(typing.NamedTuple):
    container_state: ContainerState
    results: Dict[DependantBase[Any], Any]
    dependency_counts: MutableMapping[DependantBase[Any], int]
    dependants: Mapping[DependantBase[Any], Iterable[Task[Any]]]


class Task(Generic[DependencyType]):
    __slots__ = ("dependant", "dependencies")

    def __init__(
        self,
        dependant: DependantBase[DependencyType],
        dependencies: List[DependencyParameter[Task[Any]]],
    ) -> None:
        self.dependant = dependant
        self.dependencies = dependencies

    def compute(
        self,
        state: ExecutionState,
    ) -> Union[Awaitable[Iterable[Optional[TaskInfo]]], Iterable[Optional[TaskInfo]]]:
        raise NotImplementedError

    def as_executor_task(self, state: ExecutionState) -> TaskInfo:
        raise NotImplementedError

    def gather_params(
        self, results: Dict[DependantBase[Any], Any]
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

    def gather_new_tasks(self, state: ExecutionState) -> Iterable[Optional[TaskInfo]]:
        """Look amongst our dependants to see if any of them are now dependency free"""
        new_tasks: Deque[Optional[TaskInfo]] = deque()
        for dependant in state.dependants[self.dependant]:
            count = state.dependency_counts[dependant.dependant]
            if count == 1:
                # this dependant has no further dependencies, so we can compute it now
                new_tasks.append(dependant.as_executor_task(state))
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
    __slots__ = ("is_gen", "call")

    def __init__(
        self,
        dependant: DependantBase[DependencyType],
        dependencies: List[DependencyParameter[Task[Any]]],
    ) -> None:
        super().__init__(dependant, dependencies)
        assert self.dependant.call is not None
        self.call = self.dependant.call
        self.is_gen = is_async_gen_callable(self.call)

    def as_executor_task(self, state: ExecutionState) -> AsyncTaskInfo:
        return AsyncTaskInfo(
            dependant=self.dependant,
            task=functools.partial(self.compute, state),
        )

    async def compute(
        self,
        state: ExecutionState,
    ) -> Iterable[Optional[TaskInfo]]:
        args, kwargs = self.gather_params(state.results)

        call = self.call
        if self.is_gen:
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
    __slots__ = ("is_gen", "call")

    def __init__(
        self,
        dependant: DependantBase[DependencyType],
        dependencies: List[DependencyParameter[Task[Any]]],
    ) -> None:
        super().__init__(dependant, dependencies)
        assert self.dependant.call is not None
        self.call = self.dependant.call
        self.is_gen = is_gen_callable(self.call)

    def as_executor_task(self, state: ExecutionState) -> SyncTaskInfo:
        return SyncTaskInfo(
            dependant=self.dependant,
            task=functools.partial(self.compute, state),
        )

    def compute(
        self,
        state: ExecutionState,
    ) -> Iterable[Optional[TaskInfo]]:

        args, kwargs = self.gather_params(state.results)

        call = self.call
        if self.is_gen:
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
