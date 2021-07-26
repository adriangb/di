from contextlib import AsyncExitStack
from typing import Any, AsyncContextManager, Protocol, TypeVar

T = TypeVar("T")


class LifespanPolicy(Protocol):
    async def bind_context(self, *, policy: Any, context_manager: AsyncContextManager[T]) -> T:
        raise NotImplementedError  # pragma: no cover


class AsyncExitStackLifespan(AsyncExitStack, LifespanPolicy):
    async def bind_context(self, *, policy: Any, context_manager: AsyncContextManager[T]) -> T:
        return await super().enter_async_context(context_manager)
