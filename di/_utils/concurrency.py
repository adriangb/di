import inspect
import sys
from contextlib import asynccontextmanager, contextmanager
from functools import partial
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Callable,
    ContextManager,
    Iterator,
    Optional,
    TypeVar,
    Union,
    cast,
    overload,
)

if sys.version_info < (3, 10):  # pragma: no cover
    from typing_extensions import ParamSpec
else:  # pragma: no cover
    from typing import ParamSpec

import anyio

T = TypeVar("T")


@asynccontextmanager
async def contextmanager_in_threadpool(
    cm: ContextManager[T],
    limiter: Optional[anyio.CapacityLimiter],
) -> AsyncGenerator[T, None]:
    # give each exit it's own limiter to avoid race conditions for dependencies
    # that have their own internal resource limits and may acquire a new thread
    # before they release an old one thus leaving the old resource
    # with no available threads to release itself -> deadlocks
    exit_limiter = anyio.CapacityLimiter(1)
    try:
        yield await anyio.to_thread.run_sync(cm.__enter__, limiter=limiter)
    except Exception as e:
        ok = bool(
            await anyio.to_thread.run_sync(
                cm.__exit__, type(e), e, None, limiter=exit_limiter
            )
        )
        if not ok:
            raise e
    else:
        await anyio.to_thread.run_sync(
            cm.__exit__, None, None, None, limiter=exit_limiter
        )


P = ParamSpec("P")


@overload
def as_async(  # type: ignore
    __call: Callable[P, Iterator[T]], *, limiter: Optional[anyio.CapacityLimiter] = ...
) -> Callable[P, AsyncIterator[T]]:
    ...


@overload
def as_async(
    __call: Callable[P, T], *, limiter: Optional[anyio.CapacityLimiter] = ...
) -> Callable[P, Awaitable[T]]:
    ...


def as_async(
    __call: Union[Callable[P, Iterator[T]], Callable[P, T]],
    *,
    limiter: Optional[anyio.CapacityLimiter] = None,
) -> Union[Callable[P, Awaitable[T]], Callable[P, AsyncIterator[T]]]:
    if inspect.isgeneratorfunction(__call):
        cm = cast(Callable[P, Iterator[T]], __call)

        async def wrapped_cm(*args: "P.args", **kwargs: "P.kwargs") -> AsyncIterator[T]:
            sync_cm = contextmanager(cm)(*args, **kwargs)
            async with contextmanager_in_threadpool(sync_cm, limiter=limiter) as res:
                yield res

        annotations = __call.__annotations__
        annotations["return"] = Any
        wrapped_cm.__annotations__ = annotations
        wrapped_cm.__doc__ = __call.__doc__
        sig = inspect.signature(__call)
        sig.replace(return_annotation=Any)
        wrapped_cm.__signature__ = sig  # type: ignore

        return wrapped_cm

    call = cast(Callable[P, T], __call)

    async def wrapped_callable(*args: "P.args", **kwargs: "P.kwargs") -> T:
        return await anyio.to_thread.run_sync(
            partial(call, *args, **kwargs), limiter=limiter
        )

    annotations = __call.__annotations__
    annotations["return"] = Any
    wrapped_callable.__annotations__ = annotations
    wrapped_callable.__doc__ = __call.__doc__
    sig = inspect.signature(__call)
    sig.replace(return_annotation=Any)
    wrapped_callable.__signature__ = sig  # type: ignore

    return wrapped_callable
