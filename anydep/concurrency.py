import contextvars
import functools
from contextlib import asynccontextmanager
from typing import Any, Callable, TypeVar

import anyio

T = TypeVar("T")


async def run_in_threadpool(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    # Ensure we run in the same context
    child = functools.partial(func, *args, **kwargs)
    context = contextvars.copy_context()
    func = context.run
    args = (child,)
    return await anyio.to_thread.run_sync(func, *args)


@asynccontextmanager
async def contextmanager_in_threadpool(cm: Any) -> Any:
    try:
        yield await run_in_threadpool(cm.__enter__)
    except Exception as e:
        ok = await run_in_threadpool(cm.__exit__, type(e), e, None)
        if not ok:
            raise e
    else:
        await run_in_threadpool(cm.__exit__, None, None, None)
