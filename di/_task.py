from __future__ import annotations

from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, Any, Dict, Generic, List, Tuple, cast

from di._inspect import is_async_gen_callable, is_gen_callable
from di._state import ContainerState
from di.exceptions import IncompatibleDependencyError
from di.types.dependencies import DependantProtocol, DependencyParameter
from di.types.executor import Values
from di.types.providers import (
    AsyncGeneratorProvider,
    CallableProvider,
    CoroutineProvider,
    Dependency,
    DependencyType,
    GeneratorProvider,
)


class Task(Generic[DependencyType]):
    def __init__(
        self,
        dependant: DependantProtocol[DependencyType],
        dependencies: List[DependencyParameter[Task[Dependency]]],
    ) -> None:
        self.dependant = dependant
        self.dependencies = dependencies

    def _gather_params(
        self, results: Dict[Task[Any], Any]
    ) -> Tuple[List[Dependency], Dict[str, Dependency]]:
        positional: List[Dependency] = []
        keyword: Dict[str, Dependency] = {}
        for dep in self.dependencies:
            if dep.parameter is not None:
                if dep.parameter.kind is dep.parameter.kind.POSITIONAL_ONLY:
                    positional.append(results[dep.dependency])
                else:
                    keyword[dep.parameter.name] = results[dep.dependency]
        return positional, keyword

    def use_value(
        self, state: ContainerState, results: Dict[Task[Any], Any], values: Values
    ) -> bool:
        assert self.dependant.call is not None
        if self.dependant.call in values:
            results[self] = values[self.dependant.call]
            return True
        if self.dependant.share and state.cached_values.contains(self.dependant.call):
            # use cached value
            results[self] = state.cached_values.get(self.dependant.call)
            return True
        return False


class AsyncTask(Task[DependencyType]):
    async def compute(
        self,
        state: ContainerState,
        results: Dict[Task[Any], Any],
        values: Values,
    ) -> None:
        if self.use_value(state, results, values):
            return  # pragma: no cover
        assert self.dependant.call is not None
        call = self.dependant.call
        args, kwargs = self._gather_params(results)
        if is_async_gen_callable(self.dependant.call):
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
    def compute(
        self,
        state: ContainerState,
        results: Dict[Task[Any], Any],
        values: Values,
    ) -> None:
        if self.use_value(state, results, values):
            return
        assert self.dependant.call is not None
        call = self.dependant.call
        args, kwargs = self._gather_params(results)
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
