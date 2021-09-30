import contextvars
import functools
from typing import Any, Awaitable, Callable, TypeVar, Union, cast

import anyio

from di._inspect import is_coroutine_callable

T = TypeVar("T")


def curry_context(call: Callable[..., T]) -> Callable[..., T]:
    ctx = contextvars.copy_context()

    def inner(*args: Any, **kwargs: Any) -> T:
        return ctx.run(functools.partial(call, *args, **kwargs))

    return inner


def callable_in_thread_pool(call: Callable[..., T]) -> Callable[..., Awaitable[T]]:
    def inner(*args: Any, **kwargs: Any) -> T:
        return cast(Awaitable[T], anyio.to_thread.run_sync(curry_context(call)))  # type: ignore

    return inner  # type: ignore


def gurantee_awaitable(
    call: Union[Callable[..., Awaitable[T]], Callable[..., T]]
) -> Callable[..., Awaitable[T]]:
    if not is_coroutine_callable(call):
        return callable_in_thread_pool(cast(Callable[..., T], call))
    return cast(Callable[..., Awaitable[T]], call)
