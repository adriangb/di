from contextlib import AsyncExitStack
from typing import AsyncContextManager, Protocol, TypeVar

from anydep.models import Dependant

T = TypeVar("T")


class DependencyLifespanPolicy(Protocol):
    async def bind_context(self, *, dependant: Dependant, context_manager: AsyncContextManager[T]) -> T:
        raise NotImplementedError  # pragma: no cover


class AsyncExitStackDependencyLifespan(AsyncExitStack, DependencyLifespanPolicy):
    async def bind_context(self, *, dependant: Dependant, context_manager: AsyncContextManager[T]) -> T:
        return await super().enter_async_context(context_manager)
