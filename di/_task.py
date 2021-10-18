from __future__ import annotations

import typing
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, Any, Dict, Generic, List, Tuple, cast

from di._inspect import is_async_gen_callable, is_gen_callable
from di._state import ContainerState
from di.exceptions import IncompatibleDependencyError
from di.types.dependencies import DependantProtocol, DependencyParameter
from di.types.providers import (
    AsyncGeneratorProvider,
    CallableProvider,
    CoroutineProvider,
    DependencyType,
    GeneratorProvider,
)


class Value(typing.NamedTuple):
    value: Any


class Task(Generic[DependencyType]):
    __slots__ = ("dependant", "dependencies")

    def __init__(
        self,
        dependant: DependantProtocol[DependencyType],
        dependencies: List[DependencyParameter[Task[Any]]],
    ) -> None:
        self.dependant = dependant
        self.dependencies = dependencies

    def _gather_params(
        self, results: Dict[Task[Any], Any]
    ) -> Tuple[List[Any], Dict[str, Any]]:
        positional: List[Any] = []
        keyword: Dict[str, Any] = {}
        for dep in self.dependencies:
            if dep.parameter is not None:
                if dep.parameter.kind is dep.parameter.kind.POSITIONAL_ONLY:
                    positional.append(results[dep.dependency])
                else:
                    keyword[dep.parameter.name] = results[dep.dependency]
        return positional, keyword


class AsyncTask(Task[DependencyType]):
    __slots__ = ()

    async def compute(
        self,
        state: ContainerState,
        results: Dict[Task[Any], Any],
    ) -> None:
        args, kwargs = self._gather_params(results)

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
            results[self] = await stack.enter_async_context(
                asynccontextmanager(call)(*args, **kwargs)
            )
        else:
            if TYPE_CHECKING:
                call = cast(CoroutineProvider[DependencyType], call)
            results[self] = await call(*args, **kwargs)
        if self.dependant.share:
            # caching is allowed, now that we have a value we can save it and start using the cache
            state.cached_values.set(
                self.dependant.call, results[self], scope=self.dependant.scope
            )


class SyncTask(Task[DependencyType]):
    __slots__ = ()

    def compute(
        self,
        state: ContainerState,
        results: Dict[Task[Any], Any],
    ) -> None:

        args, kwargs = self._gather_params(results)

        assert self.dependant.call is not None
        call = self.dependant.call
        if is_gen_callable(self.dependant.call):
            if TYPE_CHECKING:
                call = cast(GeneratorProvider[DependencyType], call)
            stack = state.stacks[self.dependant.scope]
            results[self] = stack.enter_context(contextmanager(call)(*args, **kwargs))
        else:
            if TYPE_CHECKING:
                call = cast(CallableProvider[DependencyType], call)
            results[self] = call(*args, **kwargs)
        if self.dependant.share:
            # caching is allowed, now that we have a value we can save it and start using the cache
            state.cached_values.set(
                self.dependant.call, results[self], scope=self.dependant.scope
            )
