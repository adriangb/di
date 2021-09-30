from __future__ import annotations

import contextvars
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    AsyncContextManager,
    ContextManager,
    Optional,
    Type,
    Union,
    cast,
)

if TYPE_CHECKING:
    from di._state import ContainerState

from di.types import FusedContextManager
from di.types.scopes import Scope


class LocalScopeContext(FusedContextManager[None]):
    def __init__(
        self, context: contextvars.ContextVar[ContainerState], scope: Scope
    ) -> None:
        self.context = context
        self.scope = scope
        self.token: Optional[contextvars.Token[ContainerState]] = None

    def __enter__(self):
        current = self.context.get()
        new = current.copy()
        self.token = self.context.set(new)
        self.state_cm = cast(ContextManager[None], new.enter_scope(self.scope))
        self.state_cm.__enter__()

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        if self.token is not None:
            self.context.reset(self.token)
        cm = cast(ContextManager[None], self.state_cm)
        return cm.__exit__(exc_type, exc_value, traceback)

    async def __aenter__(self):
        current = self.context.get()
        new = current.copy()
        self.token = self.context.set(new)
        self.state_cm = cast(AsyncContextManager[None], new.enter_scope(self.scope))
        await self.state_cm.__aenter__()

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        if self.token is not None:
            self.context.reset(self.token)
        cm = cast(AsyncContextManager[None], self.state_cm)
        return await cm.__aexit__(exc_type, exc_value, traceback)
