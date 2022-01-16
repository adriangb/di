from __future__ import annotations

from contextlib import AsyncExitStack, ExitStack
from types import TracebackType
from typing import Any, Dict, Optional, Type, Union, cast

from di._utils.scope_map import ScopeMap
from di._utils.types import FusedContextManager
from di.api.providers import DependencyProvider
from di.api.scopes import Scope


class ContainerState:
    __slots__ = ("cached_values", "stacks")

    def __init__(
        self,
        cached_values: ScopeMap[DependencyProvider, Any],
        stacks: Dict[Scope, Union[AsyncExitStack, ExitStack]],
    ) -> None:
        self.cached_values = cached_values
        self.stacks = stacks

    @staticmethod
    def initialize() -> ContainerState:
        return ContainerState(
            cached_values=ScopeMap(),
            stacks={},
        )

    def copy(self) -> ContainerState:
        return ContainerState(
            cached_values=ScopeMap(self.cached_values.copy()),
            stacks=self.stacks.copy(),
        )

    def enter_scope(self, scope: Scope) -> FusedContextManager[None]:
        """Enter a scope and get back a new ContainerState object that you can use to execute dependencies."""
        return ScopeContext(self, scope)


class ScopeContext(FusedContextManager[None]):
    __slots__ = ("state", "scope", "stack")
    stack: Union[AsyncExitStack, ExitStack]

    def __init__(self, state: ContainerState, scope: Scope) -> None:
        self.state = state
        self.scope = scope

    def __enter__(self) -> None:
        self.state.stacks[self.scope] = self.stack = ExitStack()
        self.state.cached_values.add_scope(self.scope)

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        return cast(ExitStack, self.stack).__exit__(exc_type, exc_value, traceback)

    async def __aenter__(self) -> None:
        self.state.stacks[self.scope] = self.stack = AsyncExitStack()
        self.state.cached_values.add_scope(self.scope)

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        return await cast(AsyncExitStack, self.stack).__aexit__(
            exc_type, exc_value, traceback
        )
