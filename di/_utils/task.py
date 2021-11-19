from __future__ import annotations

import functools
import typing
from collections import deque
from contextlib import asynccontextmanager, contextmanager
from typing import (
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
    TypeVar,
    Union,
)

from di._utils.inspect import is_async_gen_callable, is_gen_callable
from di._utils.state import ContainerState
from di.exceptions import IncompatibleDependencyError
from di.types.dependencies import DependantBase, DependencyParameter
from di.types.executor import AsyncTaskInfo, SyncTaskInfo, TaskInfo


class ExecutionState(typing.NamedTuple):
    container_state: ContainerState
    results: Dict[DependantBase[Any], Any]
    dependency_counts: MutableMapping[Task[Any], int]
    dependants: Mapping[Task[Any], Iterable[Task[Any]]]


DependencyType = TypeVar("DependencyType")

TaskQueue = Deque[Optional[TaskInfo]]


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
        """Compute this dependency within the context of the current state"""
        raise NotImplementedError

    def as_executor_task(self, state: ExecutionState) -> TaskInfo:
        """Bind the state and return either an AsyncTaskInfo or SyncTaskInfo"""
        raise NotImplementedError

    def gather_params(
        self, results: Dict[DependantBase[Any], Any]
    ) -> Tuple[List[Any], Dict[str, Any]]:
        """Gather all parameters (aka *args and **kwargs) needed for computation"""
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
        new_tasks: TaskQueue = deque()
        for dependant in state.dependants[self]:
            state.dependency_counts[dependant] -= 1
            if state.dependency_counts[dependant] == 0:
                # this dependant has no further dependencies, so we can compute it now
                new_tasks.append(dependant.as_executor_task(state))
        # remove ourselves if we have no deps
        if state.dependency_counts[self] == 0:
            del state.dependency_counts[self]
            if not state.dependency_counts:
                # all dependencies are taken care of, insert sentinel None value
                new_tasks.append(None)
        return new_tasks

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({repr(self.dependant)}, {repr(self.dependencies)})"


class AsyncTask(Task[DependencyType]):
    __slots__ = ("is_generator", "call")

    def __init__(
        self,
        dependant: DependantBase[DependencyType],
        dependencies: List[DependencyParameter[Task[Any]]],
    ) -> None:
        super().__init__(dependant, dependencies)
        assert self.dependant.call is not None
        self.call = self.dependant.call
        self.is_generator = is_async_gen_callable(self.call)

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
        if self.is_generator:
            stack = state.container_state.stacks[self.dependant.scope]
            try:
                enter = stack.enter_async_context  # type: ignore[union-attr]
            except AttributeError:
                raise IncompatibleDependencyError(
                    f"The dependency {self.dependant} is an awaitable dependency"
                    f" and canot be used in the sync scope {self.dependant.scope}"
                )
            state.results[self.dependant] = await enter(
                asynccontextmanager(call)(*args, **kwargs)  # type: ignore[arg-type]
            )
        else:
            state.results[self.dependant] = await call(*args, **kwargs)  # type: ignore[misc]

        return self.gather_new_tasks(state)


class SyncTask(Task[DependencyType]):
    __slots__ = ("is_generator", "call")

    def __init__(
        self,
        dependant: DependantBase[DependencyType],
        dependencies: List[DependencyParameter[Task[Any]]],
    ) -> None:
        super().__init__(dependant, dependencies)
        assert self.dependant.call is not None
        self.call = self.dependant.call
        self.is_generator = is_gen_callable(self.call)

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
        if self.is_generator:
            stack = state.container_state.stacks[self.dependant.scope]
            state.results[self.dependant] = stack.enter_context(
                contextmanager(call)(*args, **kwargs)  # type: ignore[arg-type]
            )
        else:
            state.results[self.dependant] = call(*args, **kwargs)

        return self.gather_new_tasks(state)
