from __future__ import annotations

import contextvars
from contextlib import AsyncExitStack, ExitStack, contextmanager
from types import TracebackType
from typing import (
    Any,
    ContextManager,
    Dict,
    Generator,
    List,
    Optional,
    Type,
    Union,
    cast,
)

from di._scope_map import ScopeMap
from di.types import FusedContextManager
from di.types.dependencies import DependantBase
from di.types.providers import (
    DependencyProvider,
    DependencyProviderType,
    DependencyType,
)
from di.types.scopes import Scope


class LocalScopeContext(FusedContextManager[None]):
    __slots__ = ("context", "scope", "token", "_sync_cm", "_async_cm")
    context: contextvars.ContextVar[ContainerState]
    scope: Scope
    token: contextvars.Token[ContainerState]

    def __init__(
        self, context: contextvars.ContextVar[ContainerState], scope: Scope
    ) -> None:
        self.context = context
        self.scope = scope

    def __enter__(self) -> None:
        current = self.context.get()
        new = current.copy()
        self.token = self.context.set(new)
        self._sync_cm = new.enter_scope(self.scope)
        self._sync_cm.__enter__()

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        self.context.reset(self.token)
        return self._sync_cm.__exit__(exc_type, exc_value, traceback)

    async def __aenter__(self) -> None:
        current = self.context.get()
        new = current.copy()
        self.token = self.context.set(new)
        self._async_cm = new.enter_scope(self.scope)
        await self._async_cm.__aenter__()

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        self.context.reset(self.token)
        return await self._async_cm.__aexit__(exc_type, exc_value, traceback)


class ContainerState:
    __slots__ = ("binds", "cached_values", "stacks")
    binds: Dict[DependencyProvider, DependantBase[Any]]
    cached_values: ScopeMap[DependencyProvider, Any]
    stacks: Dict[Scope, Union[AsyncExitStack, ExitStack]]

    def __init__(self) -> None:
        self.binds = {}
        self.cached_values = ScopeMap()
        self.stacks = {}

    def copy(self) -> ContainerState:
        new = ContainerState()
        new.binds = self.binds.copy()
        new.stacks = self.stacks.copy()
        new.cached_values = self.cached_values.copy()
        return new

    def enter_scope(self, scope: Scope) -> FusedContextManager[None]:
        return ScopeContext(self, scope)

    @property
    def scopes(self) -> List[Scope]:
        return list(self.stacks.keys())

    def bind(
        self,
        provider: DependantBase[DependencyType],
        dependency: DependencyProviderType[DependencyType],
    ) -> ContextManager[None]:
        previous_provider = self.binds.get(dependency, None)

        self.binds[dependency] = provider

        @contextmanager
        def unbind() -> Generator[None, None, None]:
            try:
                yield
            finally:
                self.binds.pop(dependency)
                if previous_provider is not None:
                    self.binds[dependency] = previous_provider

        return unbind()


class ScopeContext(FusedContextManager[None]):
    __slots__ = ("state", "scope")

    def __init__(self, state: ContainerState, scope: Scope) -> None:
        self.state = state
        self.scope = scope

    def __enter__(self) -> None:
        self.state.stacks[self.scope] = ExitStack()
        self.state.cached_values.add_scope(self.scope)

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        stack = self.state.stacks[self.scope]
        stack = cast(ExitStack, stack)
        self.state.stacks.pop(self.scope)
        self.state.cached_values.pop_scope(self.scope)
        return stack.__exit__(exc_type, exc_value, traceback)

    async def __aenter__(self) -> None:
        self.state.stacks[self.scope] = AsyncExitStack()
        self.state.cached_values.add_scope(self.scope)

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        stack = self.state.stacks[self.scope]
        stack = cast(AsyncExitStack, stack)
        self.state.stacks.pop(self.scope)
        self.state.cached_values.pop_scope(self.scope)
        return await stack.__aexit__(exc_type, exc_value, traceback)
