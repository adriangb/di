import contextvars
import functools
from typing import Any, Awaitable, Callable, TypeVar, Union, cast

import anyio

from di._inspect import is_coroutine_callable

T = TypeVar("T")


def callable_in_thread_pool(call: Callable[..., T]) -> Callable[..., Awaitable[T]]:
    def inner(*args: Any, **kwargs: Any) -> T:
        # Ensure we run in the same context
        child = functools.partial(call, *args, **kwargs)
        context = contextvars.copy_context()
        return cast(Awaitable[T], anyio.to_thread.run_sync(context.run, child))  # type: ignore

    return inner  # type: ignore


def gurantee_awaitable(
    call: Union[Callable[..., Awaitable[T]], Callable[..., T]]
) -> Callable[..., Awaitable[T]]:
    if not is_coroutine_callable(call):
        return callable_in_thread_pool(cast(Callable[..., T], call))
    return cast(Callable[..., Awaitable[T]], call)
