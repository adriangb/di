import concurrent.futures
import inspect
import typing
from collections import deque

import anyio
import anyio.abc

from di._concurrency import curry_context, guarantee_awaitable
from di._inspect import is_coroutine_callable
from di.types.executor import (
    AsyncExecutor,
    AsyncTaskReturnValue,
    SyncExecutor,
    SyncTaskReturnValue,
    Task,
    TaskInfo,
)


def _check_not_coro(
    task: typing.Optional[Task],
) -> typing.Callable[[], SyncTaskReturnValue]:
    if task is not None and is_coroutine_callable(task):
        raise TypeError("Cannot execute async dependencies in execute_sync")
    return task  # type: ignore[return-value]


class SimpleSyncExecutor(SyncExecutor):
    def execute_sync(self, tasks: typing.Iterable[Task]) -> None:
        q: typing.Deque[Task] = deque(tasks)
        while q:
            task = q.popleft()
            newtasks = _check_not_coro(task)()
            for newtask in newtasks:
                if newtask is None:
                    return
                else:
                    q.append(newtask.task)


class SimpleAsyncExecutor(AsyncExecutor):
    async def execute_async(self, tasks: typing.Iterable[Task]) -> None:
        q: typing.Deque[Task] = deque(tasks)
        while q:
            task = q.popleft()
            maybe_coro = task()
            if inspect.isawaitable(maybe_coro):
                newtasks = await typing.cast(AsyncTaskReturnValue, maybe_coro)
            else:
                newtasks = typing.cast(SyncTaskReturnValue, maybe_coro)
            for newtask in newtasks:
                if newtask is None:
                    return
                else:
                    q.append(newtask.task)


class ConcurrentSyncExecutor(AsyncExecutor):
    def execute_sync(self, tasks: typing.Iterable[Task]) -> None:
        futures: typing.Set[
            concurrent.futures.Future[typing.Iterable[typing.Optional[TaskInfo]]]
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
                            for future in concurrent.futures.as_completed(futures):
                                future.result()
                            return
                        futures.add(
                            exec.submit(curry_context(_check_not_coro(newtask.task)))
                        )


async def _async_worker(
    task: Task,
    send: typing.Callable[[typing.Optional[Task]], typing.Awaitable[None]],
) -> None:
    newtasks: SyncTaskReturnValue = await guarantee_awaitable(task)()  # type: ignore[assignment]
    for taskinfo in newtasks:
        if taskinfo is None:
            await send(None)
            return
        await send(taskinfo.task)


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
