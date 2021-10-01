from __future__ import annotations

from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, Any, Dict, Generic, List, Tuple, cast

from di._inspect import DependencyParameter, is_async_gen_callable, is_gen_callable
from di._state import ContainerState
from di.exceptions import IncompatibleDependencyError
from di.types.dependencies import DependantProtocol
from di.types.providers import (
    AsyncGeneratorProvider,
    CallableProvider,
    CoroutineProvider,
    Dependency,
    DependencyType,
    GeneratorProvider,
)

_UNSET = object()


class Task(Generic[DependencyType]):
    def __init__(
        self,
        dependant: DependantProtocol[DependencyType],
        dependencies: Dict[str, DependencyParameter[Task[Dependency]]],
    ) -> None:
        self.dependant = dependant
        self.dependencies = dependencies
        self._result: Any = _UNSET

    def _gather_params(self) -> Tuple[List[Dependency], Dict[str, Dependency]]:
        positional: List[Dependency] = []
        keyword: Dict[str, Dependency] = {}
        for param_name, dep in self.dependencies.items():
            if dep.parameter.kind is dep.parameter.kind.POSITIONAL_ONLY:
                positional.append(dep.dependency.get_result())
            else:
                keyword[param_name] = dep.dependency.get_result()
        return positional, keyword

    def get_result(self) -> DependencyType:
        if self._result is _UNSET:
            raise ValueError(
                "`compute()` must be called before `get_result()`; this is likely a bug!"
            )
        return self._result


class AsyncTask(Task[DependencyType]):
    async def compute(self, state: ContainerState) -> None:
        assert self.dependant.call is not None
        call = self.dependant.call
        args, kwargs = self._gather_params()

        if self.dependant.share and state.cached_values.contains(self.dependant.call):
            # use cached value
            self._result = state.cached_values.get(self.dependant.call)
        else:
            if is_async_gen_callable(self.dependant.call):
                stack = state.stacks[self.dependant.scope]
                if not isinstance(stack, AsyncExitStack):
                    raise IncompatibleDependencyError(
                        f"The dependency {self.dependant} is an awaitable dependency"
                        f" and canot be used in the sync scope {self.dependant.scope}"
                    )
                if TYPE_CHECKING:
                    call = cast(AsyncGeneratorProvider[DependencyType], call)
                self._result = await stack.enter_async_context(
                    asynccontextmanager(call)(*args, **kwargs)
                )
            else:
                if TYPE_CHECKING:
                    call = cast(CoroutineProvider[DependencyType], call)
                self._result = await call(*args, **kwargs)
            if self.dependant.share:
                # caching is allowed, now that we have a value we can save it and start using the cache
                state.cached_values.set(
                    self.dependant.call, self._result, scope=self.dependant.scope
                )


class SyncTask(Task[DependencyType]):
    def compute(self, state: ContainerState) -> None:
        assert self.dependant.call is not None
        call = self.dependant.call
        args, kwargs = self._gather_params()

        if self.dependant.share and state.cached_values.contains(self.dependant.call):
            # use cached value
            self._result = state.cached_values.get(self.dependant.call)
        else:
            if is_gen_callable(self.dependant.call):
                if TYPE_CHECKING:
                    call = cast(GeneratorProvider[DependencyType], call)
                stack = state.stacks[self.dependant.scope]
                self._result = stack.enter_context(
                    contextmanager(call)(*args, **kwargs)
                )
            else:
                if TYPE_CHECKING:
                    call = cast(CallableProvider[DependencyType], call)
                self._result = call(*args, **kwargs)
            if self.dependant.share:
                # caching is allowed, now that we have a value we can save it and start using the cache
                state.cached_values.set(
                    self.dependant.call, self._result, scope=self.dependant.scope
                )
