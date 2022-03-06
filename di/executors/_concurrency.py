import contextvars
from typing import Any, Awaitable, Callable, TypeVar

import anyio

T = TypeVar("T")


def callable_in_thread_pool(call: Callable[..., T]) -> Callable[..., Awaitable[T]]:
    def inner(*args: Any, **kwargs: Any) -> "Awaitable[T]":
        return anyio.to_thread.run_sync(
            contextvars.copy_context().run, lambda: call(*args, **kwargs)
        )  # type: ignore[return-value]

    return inner
