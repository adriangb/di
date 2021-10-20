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
    DependencyProvider,
    DependencyType,
    GeneratorProvider,
)


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
        state: ContainerState,
        results: Dict[DependantProtocol[Any], Any],
        values: typing.Mapping[DependencyProvider, Any],
        dependency_counts: MutableMapping[DependantProtocol[Any], int],
        dependants: MutableMapping[DependantProtocol[Any], List[Task[Any]]],
    ) -> Union[
        Awaitable[Iterable[Optional[ExecutorTask]]], Iterable[Optional[ExecutorTask]]
    ]:
        raise NotImplementedError

    def from_cache_or_values(
        self,
        state: ContainerState,
        results: Dict[DependantProtocol[Any], Any],
        values: typing.Mapping[DependencyProvider, Any],
    ) -> bool:
        assert self.dependant.call is not None
        if self.dependant.call in values:
            value = values[self.dependant.call]
            results[self.dependant] = value
            if self.dependant.share:
                state.cached_values.set(
                    self.dependant.call, value, scope=self.dependant.scope
                )
            return True
        elif self.dependant.share and state.cached_values.contains(self.dependant.call):
            results[self.dependant] = state.cached_values.get(self.dependant.call)
            return True
        return False

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
        self,
        state: ContainerState,
        results: Dict[DependantProtocol[Any], Any],
        values: typing.Mapping[DependencyProvider, Any],
        dependency_counts: MutableMapping[DependantProtocol[Any], int],
        dependants: MutableMapping[DependantProtocol[Any], List[Task[Any]]],
    ) -> Iterable[Optional[ExecutorTask]]:
        """Look amongst our dependants to see if any of them are now dependency free"""
        new_tasks: Deque[Optional[ExecutorTask]] = deque()
        for dependant in dependants[self.dependant]:
            count = dependency_counts[dependant.dependant]
            if count == 1:
                # this dependant has no further dependencies, so we can compute it now
                newtask = functools.partial(
                    dependant.compute,
                    state=state,
                    results=results,
                    values=values,
                    dependency_counts=dependency_counts,
                    dependants=dependants,
                )
                new_tasks.append(newtask)  # type: ignore[arg-type] # because of partial
                # pop it from dependency counts so that we can
                # tell when we've satisfied all dependencies below
                dependency_counts.pop(dependant.dependant)
            else:
                dependency_counts[dependant.dependant] = count - 1
        # also pop ourselves if we have no deps
        if dependency_counts.get(self.dependant, -1) == 0:
            dependency_counts.pop(self.dependant)
        if not dependency_counts:
            # all dependencies are taken care of, insert sentinel None value
            new_tasks.append(None)
        return new_tasks

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({repr(self.dependant)}, {repr(self.dependencies)})"


class AsyncTask(Task[DependencyType]):
    __slots__ = ()

    async def compute(
        self,
        state: ContainerState,
        results: Dict[DependantProtocol[Any], Any],
        values: typing.Mapping[DependencyProvider, Any],
        dependency_counts: MutableMapping[DependantProtocol[Any], int],
        dependants: MutableMapping[DependantProtocol[Any], List[Task[Any]]],
    ) -> Iterable[Optional[ExecutorTask]]:
        args, kwargs = self.gather_params(results)

        assert self.dependant.call is not None
        call = self.dependant.call
        if is_async_gen_callable(call):
            stack = state.stacks[self.dependant.scope]
            if not isinstance(stack, AsyncExitStack):
                raise IncompatibleDependencyError(
                    f"The dependency {self.dependant} is an awaitable dependency"
                    f" and canot be used in the sync scope {self.dependant.scope}"
                )
            if TYPE_CHECKING:
                call = cast(AsyncGeneratorProvider[DependencyType], call)
            results[self.dependant] = await stack.enter_async_context(
                asynccontextmanager(call)(*args, **kwargs)
            )
        else:
            if TYPE_CHECKING:
                call = cast(CoroutineProvider[DependencyType], call)
            results[self.dependant] = await call(*args, **kwargs)
        if self.dependant.share:
            # caching is allowed, now that we have a value we can save it and start using the cache
            state.cached_values.set(
                self.dependant.call, results[self.dependant], scope=self.dependant.scope
            )

        return self.gather_new_tasks(
            state=state,
            results=results,
            values=values,
            dependency_counts=dependency_counts,
            dependants=dependants,
        )


class SyncTask(Task[DependencyType]):
    __slots__ = ()

    def compute(
        self,
        state: ContainerState,
        results: Dict[DependantProtocol[Any], Any],
        values: typing.Mapping[DependencyProvider, Any],
        dependency_counts: MutableMapping[DependantProtocol[Any], int],
        dependants: MutableMapping[DependantProtocol[Any], List[Task[Any]]],
    ) -> Iterable[Optional[ExecutorTask]]:

        args, kwargs = self.gather_params(results)

        assert self.dependant.call is not None
        call = self.dependant.call
        if is_gen_callable(self.dependant.call):
            if TYPE_CHECKING:
                call = cast(GeneratorProvider[DependencyType], call)
            stack = state.stacks[self.dependant.scope]
            results[self.dependant] = stack.enter_context(
                contextmanager(call)(*args, **kwargs)
            )
        else:
            if TYPE_CHECKING:
                call = cast(CallableProvider[DependencyType], call)
            results[self.dependant] = call(*args, **kwargs)
        if self.dependant.share:
            # caching is allowed, now that we have a value we can save it and start using the cache
            state.cached_values.set(
                self.dependant.call, results[self.dependant], scope=self.dependant.scope
            )

        return self.gather_new_tasks(
            state=state,
            results=results,
            values=values,
            dependency_counts=dependency_counts,
            dependants=dependants,
        )
