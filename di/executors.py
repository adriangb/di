import concurrent.futures
import inspect
import typing
from collections import deque

import anyio
import anyio.abc

from di._concurrency import curry_context, guarantee_awaitable
from di._inspect import is_coroutine_callable
from di.types.executor import AsyncExecutor, SyncExecutor, Task


def _check_not_coro(
    task: typing.Optional[Task],
) -> typing.Callable[[], typing.Iterable[typing.Optional[Task]]]:
    if task is not None and is_coroutine_callable(task):
        raise TypeError("Cannot execute async dependencies in execute_sync")
    return task  # type: ignore[return-value]


_AsyncTaskRetval = typing.Awaitable[typing.Union[None, typing.Iterable[Task]]]
_SyncTaskRetval = typing.Union[None, typing.Iterable[Task]]


class SimpleSyncExecutor(SyncExecutor):
    def execute_sync(self, tasks: typing.Iterable[Task]) -> None:
        q: typing.Deque[typing.Optional[Task]] = deque(tasks)
        while q:
            task = q.popleft()
            if task is None:
                return
            newtasks = _check_not_coro(task)()
            assert not isinstance(newtasks, typing.Awaitable)
            q.extend(newtasks)


class SimpleAsyncExecutor(AsyncExecutor):
    async def execute_async(self, tasks: typing.Iterable[Task]) -> None:
        q: typing.Deque[Task] = deque(tasks)
        while q:
            task = q.popleft()
            maybe_coro = task()
            if inspect.isawaitable(maybe_coro):
                newtasks = await typing.cast(_AsyncTaskRetval, maybe_coro)
            else:
                newtasks = typing.cast(_SyncTaskRetval, maybe_coro)
            if newtasks is None:
                return
            q.extend(newtasks)


class ConcurrentSyncExecutor(AsyncExecutor):
    def execute_sync(self, tasks: typing.Iterable[Task]) -> None:
        futures: typing.Set[
            concurrent.futures.Future[typing.Iterable[typing.Optional[Task]]]
        ] = set()
        with concurrent.futures.ThreadPoolExecutor() as exec:
            for task in tasks:
                futures.add(exec.submit(curry_context(_check_not_coro(task))))
            while futures:
                for future in concurrent.futures.as_completed(futures):
                    newtasks = future.result()
                    futures.remove(future)
                    if inspect.isawaitable(newtasks):
                        raise TypeError(
                            "Cannot execute async dependencies in execute_sync"
                        )
                    for newtask in newtasks:
                        if newtask is None:
                            break
                        futures.add(
                            exec.submit(curry_context(_check_not_coro(newtask)))
                        )


async def _async_worker(
    task: Task,
    send: typing.Callable[[typing.Optional[Task]], typing.Awaitable[None]],
) -> None:
    newtasks: _SyncTaskRetval = await guarantee_awaitable(task)()  # type: ignore[assignment]
    if newtasks is None:
        await send(None)
        return
    for task in newtasks:
        await send(task)


Streams = typing.Tuple[
    anyio.abc.ObjectSendStream[typing.Optional[Task]],
    anyio.abc.ObjectReceiveStream[typing.Optional[Task]],
]


class ConcurrentAsyncExecutor(AsyncExecutor):
    async def execute_async(self, tasks: typing.Iterable[Task]) -> None:
        streams = typing.cast(Streams, anyio.create_memory_object_stream(float("inf")))
        send, receive = streams
        for task in tasks:
            await send.send(task)
        async with send, receive:
            async with anyio.create_task_group() as taskgroup:
                while True:
                    newtask = await receive.receive()
                    if newtask is None:
                        return None
                    taskgroup.start_soon(_async_worker, newtask, send.send)


class DefaultExecutor(ConcurrentSyncExecutor, ConcurrentAsyncExecutor):
    ...
