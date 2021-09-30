from typing import AsyncContextManager, ContextManager, TypeVar

T = TypeVar("T")


class FusedContextManager(AsyncContextManager[T], ContextManager[T]):
    ...
