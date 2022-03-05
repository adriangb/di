from __future__ import annotations

import contextvars
from types import TracebackType
from typing import Optional, Sequence, Type, TypeVar, Union

from di._utils.types import FusedContextManager
from di.api.dependencies import DependantBase
from di.api.scopes import Scope
from di.api.solved import SolvedDependant
from di.container._common import ContainerCommon
from di.container._state import ContainerState

T = TypeVar("T")


class Container(ContainerCommon):
    """A container that manages it's own state via ContextVars"""

    __slots__ = ("_scopes", "_context")

    _context: contextvars.ContextVar[ContainerState]

    def __init__(
        self,
        *,
        scopes: Sequence[Scope] = (None,),
    ) -> None:
        super().__init__()
        self._scopes = scopes
        self._context = contextvars.ContextVar(f"{self}._context")
        self._context.set(ContainerState.initialize())

    @property
    def _state(self) -> ContainerState:
        return self._context.get()

    def copy(self: _ContainerType) -> _ContainerType:
        new = object.__new__(self.__class__)
        new._scopes = self._scopes
        new._register_hooks = self._register_hooks
        new._context = self._context
        return new  # type: ignore[no-any-return]

    def solve(
        self, dependency: DependantBase[T], scopes: Optional[Sequence[Scope]] = None
    ) -> SolvedDependant[T]:
        return super().solve(dependency=dependency, scopes=scopes or self._scopes)

    def enter_scope(
        self: _ContainerType, scope: Scope
    ) -> FusedContextManager[_ContainerType]:
        new = self.copy()
        return _ContextVarStateManager(
            self._context, scope, new  # type: ignore[attr-defined]
        )


_ContainerType = TypeVar("_ContainerType", bound=Container)


class _ContextVarStateManager(FusedContextManager[_ContainerType]):
    __slots__ = ("scope", "container", "context", "cm", "token")

    cm: FusedContextManager[None]

    def __init__(
        self,
        context: contextvars.ContextVar[ContainerState],
        scope: Scope,
        container: _ContainerType,
    ) -> None:
        self.context = context
        self.scope = scope
        self.container = container

    def __enter__(self) -> _ContainerType:
        new_state = self.context.get().copy()
        self.cm = new_state.enter_scope(self.scope)
        self.cm.__enter__()
        self.token = self.context.set(new_state)
        return self.container

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        self.context.reset(self.token)
        return self.cm.__exit__(exc_type, exc_value, traceback)

    async def __aenter__(self) -> _ContainerType:
        new_state = self.context.get().copy()
        self.cm = new_state.enter_scope(self.scope)
        await self.cm.__aenter__()
        self.token = self.context.set(new_state)
        return self.container

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        self.context.reset(self.token)
        return await self.cm.__aexit__(exc_type, exc_value, traceback)
