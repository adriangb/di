from __future__ import annotations

from types import TracebackType
from typing import Optional, Type, TypeVar, Union

from di._utils.types import FusedContextManager
from di.api.scopes import Scope
from di.container._common import ContainerCommon
from di.container._state import ContainerState, SupportsScopes


class BaseContainer(ContainerCommon):
    """Basic container that lets you manage it's state yourself"""

    __slots__ = ("__state",)
    __state: ContainerState

    def __init__(self) -> None:
        super().__init__()
        self.__state = ContainerState.initialize()

    @property
    def state(self) -> SupportsScopes:
        return self.__state

    @property
    def _state(self) -> ContainerState:
        return self.__state

    def copy(self: _BaseContainerType) -> _BaseContainerType:
        new = object.__new__(self.__class__)
        # binds are use_cached
        new._register_hooks = self._register_hooks
        # cached values and scopes are not use_cached
        new.__state = self.__state.copy()
        return new  # type: ignore[no-any-return]

    def enter_scope(
        self: _BaseContainerType, scope: Scope
    ) -> FusedContextManager[_BaseContainerType]:
        """Enter a scope and get back a new BaseContainer in that scope"""
        new = self.copy()
        return _ContainerScopeContext(scope, new, new._state)


_BaseContainerType = TypeVar("_BaseContainerType", bound=BaseContainer)


class _ContainerScopeContext(FusedContextManager[_BaseContainerType]):
    __slots__ = ("scope", "container", "state", "cm")
    cm: FusedContextManager[None]

    def __init__(
        self,
        scope: Scope,
        container: _BaseContainerType,
        state: ContainerState,
    ) -> None:
        self.scope = scope
        self.container = container
        self.state = state

    def __enter__(self) -> _BaseContainerType:
        self.cm = self.state.enter_scope(self.scope)
        self.cm.__enter__()
        return self.container

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        return self.cm.__exit__(exc_type, exc_value, traceback)

    async def __aenter__(self) -> _BaseContainerType:
        self.cm = self.state.enter_scope(self.scope)
        await self.cm.__aenter__()
        return self.container

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        return await self.cm.__aexit__(exc_type, exc_value, traceback)
