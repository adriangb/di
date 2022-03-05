from __future__ import annotations

from contextlib import AsyncExitStack, ExitStack
from types import TracebackType
from typing import Any, Dict, Iterable, Optional, Type, Union

from di._utils.scope_map import ScopeMap
from di._utils.types import CacheKey, FusedContextManager
from di._utils.typing import Protocol
from di.api.scopes import Scope


class SupportsScopes(Protocol):
    @property
    def scopes(self) -> Iterable[Scope]:
        ...


class ContainerState:
    __slots__ = ("cached_values", "stacks")

    def __init__(
        self,
        cached_values: Optional[ScopeMap[CacheKey, Any]] = None,
        stacks: Optional[Dict[Scope, Union[AsyncExitStack, ExitStack]]] = None,
    ) -> None:
        self.cached_values = cached_values or ScopeMap()
        self.stacks = stacks or {}

    @property
    def scopes(self) -> Iterable[Scope]:
        return self.cached_values.keys()

    def enter_scope(self, scope: Scope) -> FusedContextManager[ContainerState]:
        """Enter a scope and get back a new ContainerState object that you can use to execute dependencies."""
        new = ContainerState(
            cached_values=ScopeMap(self.cached_values.copy()),
            stacks=self.stacks.copy(),
        )
        return ScopeContext(new, scope)


class ScopeContext(FusedContextManager[ContainerState]):
    __slots__ = ("state", "scope", "stack")
    stack: Union[AsyncExitStack, ExitStack]

    def __init__(self, state: ContainerState, scope: Scope) -> None:
        self.state = state
        self.scope = scope

    def __enter__(self) -> ContainerState:
        self.state.stacks[self.scope] = self.stack = ExitStack()
        self.state.cached_values.add_scope(self.scope)
        return self.state

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        return self.stack.__exit__(exc_type, exc_value, traceback)  # type: ignore[union-attr,no-any-return]

    async def __aenter__(self) -> ContainerState:
        self.state.stacks[self.scope] = self.stack = AsyncExitStack()
        self.state.cached_values.add_scope(self.scope)
        return self.state

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        return await self.stack.__aexit__(exc_type, exc_value, traceback)  # type: ignore[union-attr,no-any-return]
