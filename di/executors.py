import concurrent.futures
import typing
from collections import deque

import anyio
import anyio.abc

from di._concurrency import callable_in_thread_pool, curry_context
from di.types.executor import (
    AsyncExecutor,
    AsyncTaskInfo,
    SyncExecutor,
    SyncTaskInfo,
    TaskInfo,
)


class SimpleSyncExecutor(SyncExecutor):
    def execute_sync(self, tasks: typing.Iterable[TaskInfo]) -> None:
        q: typing.Deque[TaskInfo] = deque(tasks)
        while q:
            task = q.popleft()
            if type(task) is AsyncTaskInfo:
                raise TypeError("Cannot execute async dependencies in execute_sync")
            task = typing.cast(SyncTaskInfo, task)
            newtasks = task.task()
            for newtask in newtasks:
                if newtask is None:
                    return
                else:
                    q.append(newtask)


class SimpleAsyncExecutor(AsyncExecutor):
    async def execute_async(self, tasks: typing.Iterable[TaskInfo]) -> None:
        q: typing.Deque[TaskInfo] = deque(tasks)
        while q:
            task = q.popleft()
            if isinstance(task, AsyncTaskInfo):
                newtasks = await task.task()
            else:
                newtasks = task.task()
            for newtask in newtasks:
                if newtask is None:
                    return
                else:
                    q.append(newtask)


class ConcurrentSyncExecutor(AsyncExecutor):
    def execute_sync(self, tasks: typing.Iterable[TaskInfo]) -> None:
        futures: typing.Set[
            concurrent.futures.Future[typing.Iterable[typing.Optional[TaskInfo]]]
        ] = set()
        q: typing.Deque[typing.Optional[TaskInfo]] = deque(tasks)
        with concurrent.futures.ThreadPoolExecutor() as exec:
            while True:
                for future in futures.copy():
                    if future.done():
                        future.result()  # maybe error
                        futures.remove(future)
                newtasks = list(q)
                q.clear()
                for task in newtasks:
                    if task is None:
                        for future in concurrent.futures.as_completed(futures):
                            future.result()
                        return
                    if type(task) is AsyncTaskInfo:
                        raise TypeError(
                            "Cannot execute async dependencies in execute_sync"
                        )
                    task = typing.cast(SyncTaskInfo, task)
                    if (
                        getattr(task.dependant, "sync_to_thread", False) is True
                    ):  # instance of Dependant
                        call = task.task
                        exec.submit(curry_context(lambda: q.extend(call())))
                    else:
                        q.extend(task.task())


async def _async_worker(
    task: TaskInfo,
    send: typing.Callable[[typing.Optional[TaskInfo]], typing.Awaitable[None]],
) -> None:
    if type(task) is AsyncTaskInfo:
        newtasks = await task.task()
    else:
        task = typing.cast(SyncTaskInfo, task)
        if (
            getattr(task.dependant, "sync_to_thread", False) is True
        ):  # instance of Dependant
            newtasks = await callable_in_thread_pool(task.task)()
        else:
            newtasks = task.task()
    for taskinfo in newtasks:
        if taskinfo is None:
            await send(None)
            return
        await send(taskinfo)


Streams = typing.Tuple[
    anyio.abc.ObjectSendStream[typing.Optional[TaskInfo]],
    anyio.abc.ObjectReceiveStream[typing.Optional[TaskInfo]],
]


class ConcurrentAsyncExecutor(AsyncExecutor):
    async def execute_async(self, tasks: typing.Iterable[TaskInfo]) -> None:
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
