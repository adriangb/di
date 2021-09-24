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
    cast,
)

import anyio

from di._inspect import is_async_gen_callable, is_coroutine_callable, is_gen_callable
from di.dependency import (
    AsyncGeneratorProvider,
    CallableProvider,
    CoroutineProvider,
    DependencyProviderType,
    DependencyType,
    GeneratorProvider,
)

T = TypeVar("T")


def callable_in_thread_pool(call: Callable[..., T]) -> Callable[..., Awaitable[T]]:
    async def inner(*args: Any, **kwargs: Any) -> T:
        # Ensure we run in the same context
        child = functools.partial(call, *args, **kwargs)
        context = contextvars.copy_context()
        return cast(T, await anyio.to_thread.run_sync(context.run, child))

    return inner


def context_manager_in_threadpool(
    call: Callable[..., ContextManager[T]]
) -> Callable[..., AsyncContextManager[T]]:
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
    async def inner(*args: Any, **kwargs: Any):
        return await stack.enter_async_context(cm(*args, **kwargs))

    return inner


def bind_sync_context_manager(
    cm: Callable[..., ContextManager[T]], stack: AsyncExitStack
) -> Callable[..., Awaitable[T]]:
    return bind_async_context_manager(context_manager_in_threadpool(cm), stack)


def wrap_call(
    call: DependencyProviderType[DependencyType], stack: AsyncExitStack
) -> Callable[..., Awaitable[DependencyType]]:
    if is_async_gen_callable(call):
        call = cast(AsyncGeneratorProvider[DependencyType], call)
        return bind_async_context_manager(asynccontextmanager(call), stack)
    if is_gen_callable(call):
        call = cast(GeneratorProvider[DependencyType], call)
        return bind_sync_context_manager(contextmanager(call), stack)
    if not is_coroutine_callable(call):
        call = cast(CallableProvider[DependencyType], call)
        return callable_in_thread_pool(call)
    call = cast(CoroutineProvider[DependencyType], call)
    return call
