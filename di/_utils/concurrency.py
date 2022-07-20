import inspect
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from functools import partial, wraps
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Callable,
    ContextManager,
    Iterator,
    Optional,
    ParamSpec,
    TypeVar,
    Union,
    cast,
    overload,
)

import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

T = TypeVar("T")


def cm_thead_worker(
    cm: ContextManager[T],
    res_stream: MemoryObjectSendStream[T],
    err_stream: MemoryObjectReceiveStream[Optional[Exception]],
) -> None:
    with cm as res:
        anyio.from_thread.run(res_stream.send, res)
        exc = anyio.from_thread.run(err_stream.receive)
        if exc:
            raise exc


@asynccontextmanager
async def contextmanager_in_threadpool(
    cm: ContextManager[T],
) -> AsyncGenerator[T, None]:
    # streams for the data
    send_res, rcv_res = anyio.create_memory_object_stream(  # type: ignore
        float("inf"), item_type=Any
    )
    # streams for exceptions
    send_err, rcv_err = anyio.create_memory_object_stream(  # type: ignore
        float("inf"), item_type=Optional[Exception]
    )

    async with AsyncExitStack() as stack:
        stack.enter_context(rcv_res)
        stack.enter_context(rcv_err)
        stack.enter_context(send_res)
        stack.enter_context(send_err)
        async with anyio.create_task_group() as tg:
            tg.start_soon(
                anyio.to_thread.run_sync, cm_thead_worker, cm, send_res, rcv_err
            )
            res = await rcv_res.receive()
            try:
                yield res
            except Exception as e:
                await send_err.send(e)
            else:
                await send_err.send(None)


P = ParamSpec("P")


@overload
def as_async(  # type: ignore
    __call: Callable[P, Iterator[T]],
) -> Callable[P, AsyncIterator[T]]:
    ...


@overload
def as_async(
    __call: Callable[P, T],
) -> Callable[P, Awaitable[T]]:
    ...


def as_async(
    __call: Union[Callable[P, Iterator[T]], Callable[P, T]],
) -> Union[Callable[P, Awaitable[T]], Callable[P, AsyncIterator[T]]]:
    if inspect.isgeneratorfunction(__call):
        cm = cast(Callable[P, Iterator[T]], __call)

        @wraps(cm, assigned=("__doc__", "__name__", "__module__"))
        async def wrapped_cm(*args: "P.args", **kwargs: "P.kwargs") -> AsyncIterator[T]:
            sync_cm = contextmanager(cm)(*args, **kwargs)
            async with contextmanager_in_threadpool(sync_cm) as res:
                yield res

        annotations = __call.__annotations__
        annotations["return"] = Any
        wrapped_cm.__annotations__ = annotations
        sig = inspect.signature(__call)
        sig.replace(return_annotation=Any)
        wrapped_cm.__signature__ = sig  # type: ignore

        return wrapped_cm

    call = cast(Callable[P, T], __call)

    @wraps(call, assigned=("__doc__", "__name__", "__module__", "__annotations__"))
    async def wrapped_callable(*args: "P.args", **kwargs: "P.kwargs") -> T:
        return await anyio.to_thread.run_sync(partial(call, *args, **kwargs))

    annotations = __call.__annotations__
    annotations["return"] = Any
    wrapped_callable.__annotations__ = annotations
    sig = inspect.signature(__call)
    sig.replace(return_annotation=Any)
    wrapped_callable.__signature__ = sig  # type: ignore

    return wrapped_callable
