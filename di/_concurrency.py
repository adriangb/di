import contextvars
import functools
from typing import TYPE_CHECKING, Any, Awaitable, Callable, TypeVar, Union, cast

import anyio

from di._inspect import is_coroutine_callable

T = TypeVar("T")


def curry_context(call: Callable[..., T]) -> Callable[..., T]:
    ctx = contextvars.copy_context()

    def inner(*args: Any, **kwargs: Any) -> T:
        return ctx.run(functools.partial(call, *args, **kwargs))

    return inner


def callable_in_thread_pool(call: Callable[..., T]) -> Callable[..., Awaitable[T]]:
    def inner(*args: Any, **kwargs: Any) -> Awaitable[T]:
        return anyio.to_thread.run_sync(curry_context(call), *args, **kwargs)  # type: ignore

    return inner


def gurantee_awaitable(
    call: Union[Callable[..., Awaitable[T]], Callable[..., T]]
) -> Callable[..., Awaitable[T]]:
    if not is_coroutine_callable(call):
        if TYPE_CHECKING:
            call = cast(Callable[..., T], call)
        return callable_in_thread_pool(call)
    return call  # type: ignore
