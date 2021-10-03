from __future__ import annotations

import contextvars
from types import TracebackType
from typing import TYPE_CHECKING, Optional, Type, Union

if TYPE_CHECKING:
    from di._state import ContainerState  # pragma: no cover

from di.types import FusedContextManager
from di.types.scopes import Scope


class LocalScopeContext(FusedContextManager[None]):
    context: contextvars.ContextVar[ContainerState]
    scope: Scope
    token: contextvars.Token[ContainerState]

    def __init__(
        self, context: contextvars.ContextVar[ContainerState], scope: Scope
    ) -> None:
        self.context = context
        self.scope = scope

    def __enter__(self):
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

    async def __aenter__(self):
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
