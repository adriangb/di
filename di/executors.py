import concurrent.futures
import inspect
import typing
from collections import deque
from queue import Queue

import anyio
import anyio.abc

from di._concurrency import curry_context, gurantee_awaitable
from di._inspect import is_coroutine_callable
from di.types.executor import AsyncExecutor, SyncExecutor, Task


class SimpleSyncExecutor(SyncExecutor):
    def execute_sync(self, tasks: typing.Iterable[Task]) -> None:
        q: typing.Deque[typing.Optional[Task]] = deque(tasks)
        while q:
            task = q.popleft()
            if task is None:
                return
            if is_coroutine_callable(task):
                raise TypeError("Cannot execute async dependencies in execute_sync")
            newtasks = task()
            assert not isinstance(newtasks, typing.Awaitable)
            q.extend(newtasks)


class SimpleAsyncExecutor(AsyncExecutor):
    async def execute_async(self, tasks: typing.Iterable[Task]) -> None:
        q: typing.Deque[typing.Optional[Task]] = deque(tasks)
        while q:
            task = q.popleft()
            if task is None:
                return
            newtasks = task()
            if inspect.isawaitable(newtasks):
                assert isinstance(newtasks, typing.Awaitable)
                newtasks = await newtasks
            assert not isinstance(newtasks, typing.Awaitable)
            q.extend(newtasks)


def _sync_worker(task: Task, queue: Queue[typing.Optional[Task]]) -> None:
    try:
        newtasks = task()
        assert not isinstance(newtasks, typing.Awaitable)
        for newtask in newtasks:
            queue.put(newtask)
    finally:
        queue.task_done()


class ConcurrentSyncExecutor(AsyncExecutor):
    def execute_sync(self, tasks: typing.Iterable[Task]) -> None:
        queue: Queue[typing.Optional[Task]] = Queue()
        for task in tasks:
            queue.put(task)
        futures: typing.Set[concurrent.futures.Future[None]] = set()
        with concurrent.futures.ThreadPoolExecutor() as exec:
            while True:
                newtask = queue.get()
                if is_coroutine_callable(newtask):
                    raise TypeError("Cannot execute async dependencies in execute_sync")
                if newtask is None:
                    queue.task_done()
                    queue.join()
                    for future in concurrent.futures.as_completed(futures):
                        future.result()
                    return
                # check for errors
                _, futures = concurrent.futures.wait(
                    futures, return_when=concurrent.futures.FIRST_EXCEPTION
                )
                futures.add(exec.submit(_sync_worker, curry_context(newtask), queue))


async def _async_worker(
    task: Task, stream: anyio.abc.ObjectSendStream[typing.Optional[Task]]
) -> None:
    newtasks: typing.Iterable[typing.Optional[Task]] = await gurantee_awaitable(task)()  # type: ignore
    for newtask in newtasks:
        try:
            await stream.send(newtask)
        except anyio.ClosedResourceError:
            if newtask is None:
                # extra sentinel, ignore
                return None
            raise


class ConcurrentAsyncExecutor(AsyncExecutor):
    async def execute_async(self, tasks: typing.Iterable[Task]) -> None:
        send, receive = anyio.create_memory_object_stream(
            float("inf"), item_type=typing.Optional[Task]
        )
        for task in tasks:
            await send.send(task)
        async with anyio.create_task_group() as taskgroup, send, receive:
            while True:
                task = await receive.receive()
                if task is None:
                    return None
                taskgroup.start_soon(_async_worker, task, send)


class DefaultExecutor(ConcurrentSyncExecutor, ConcurrentAsyncExecutor):
    ...
