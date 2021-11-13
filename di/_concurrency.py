import contextvars
import functools
from typing import Any, Awaitable, Callable, TypeVar

import anyio

T = TypeVar("T")


def curry_context(call: Callable[..., T]) -> Callable[..., T]:
    ctx = contextvars.copy_context()

    def inner(*args: Any, **kwargs: Any) -> T:
        return ctx.run(functools.partial(call, *args, **kwargs))

    return inner


def callable_in_thread_pool(call: Callable[..., T]) -> Callable[..., Awaitable[T]]:
    def inner(*args: Any, **kwargs: Any) -> Awaitable[T]:
        return anyio.to_thread.run_sync(curry_context(call), *args, **kwargs)

    return inner
