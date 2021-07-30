import contextvars
import functools
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from typing import (
    Any,
    AsyncContextManager,
    AsyncGenerator,
    Awaitable,
    Callable,
    ContextManager,
    TypeVar,
)

import anyio

from anydep.inspect import is_async_gen_callable, is_coroutine_callable, is_gen_callable

T = TypeVar("T")


def callable_in_thread_pool(call: Callable[..., T]) -> Callable[..., Awaitable[T]]:
    async def inner(*args: Any, **kwargs: Any) -> T:
        # Ensure we run in the same context
        child = functools.partial(call, *args, **kwargs)
        context = contextvars.copy_context()
        func = context.run
        args = (child,)
        return await anyio.to_thread.run_sync(func, *args)

    return inner


def context_manager_in_threadpool(call: Callable[..., ContextManager[T]]) -> Callable[..., AsyncContextManager[T]]:
    @asynccontextmanager
    async def inner(*args: Any, **kwds: Any) -> AsyncGenerator[T, None]:
        cm = call(*args, **kwds)
        try:
            yield await callable_in_thread_pool(cm.__enter__)()
        except Exception as e:
            ok = await callable_in_thread_pool(cm.__exit__)(type(e), e, None)
            if not ok:
                raise e
        else:
            await callable_in_thread_pool(cm.__exit__)(None, None, None)

    return inner


def bind_async_context_manager(
    cm: Callable[..., AsyncContextManager[T]], stack: AsyncExitStack
) -> Callable[..., Awaitable[T]]:
    async def inner(*args, **kwargs):
        return await stack.enter_async_context(cm(*args, **kwargs))

    return inner


def bind_sync_context_manager(
    cm: Callable[..., ContextManager[T]], stack: AsyncExitStack
) -> Callable[..., Awaitable[T]]:
    return bind_async_context_manager(context_manager_in_threadpool(cm), stack)


def wrap_call(call, stack):
    if is_async_gen_callable(call):
        call = bind_async_context_manager(asynccontextmanager(call), stack)
    elif is_gen_callable(call):
        call = bind_sync_context_manager(contextmanager(call), stack)
    elif not is_coroutine_callable(call):
        call = callable_in_thread_pool(call)
    return call
