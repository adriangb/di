import concurrent.futures
import inspect
import typing

import anyio
import anyio.abc

from di._concurrency import curry_context, gurantee_awaitable
from di.types.executor import AsyncExecutor, SyncExecutor, Task, Values

ResultType = typing.TypeVar("ResultType")


class SimpleSyncExecutor(SyncExecutor):
    def execute_sync(
        self,
        tasks: typing.List[typing.List[Task]],
        get_result: typing.Callable[[], ResultType],
        values: Values,
    ) -> ResultType:
        for task_group in tasks:
            for task in task_group:
                result = task(values)
                if inspect.isawaitable(result):
                    raise TypeError("Cannot execute async dependencies in execute_sync")
        return get_result()


class ConcurrentAsyncExecutor(AsyncExecutor):
    async def execute_async(
        self,
        tasks: typing.List[typing.List[Task]],
        get_result: typing.Callable[[], ResultType],
        values: Values,
    ) -> ResultType:
        # note: there are 2 task group concepts in this function that should not be confused
        # to di, tasks groups are a set of Task's that can be executed in parallel
        # to anyio, a TaskGroup is a primitive equivalent to a Trio nursery
        tg: typing.Optional[anyio.abc.TaskGroup] = None
        for task_group in tasks:
            if len(task_group) > 1:
                if tg is None:
                    tg = anyio.create_task_group()
                async with tg:
                    for task in task_group:
                        tg.start_soon(gurantee_awaitable(task), values)  # type: ignore
            else:
                await gurantee_awaitable(next(iter(task_group)))(values)
        return get_result()


class ConcurrentSyncExecutor(SyncExecutor):
    def __init__(self) -> None:
        self._threadpool = concurrent.futures.ThreadPoolExecutor()

    def execute_sync(
        self,
        tasks: typing.List[typing.List[Task]],
        get_result: typing.Callable[[], ResultType],
        values: Values,
    ) -> ResultType:
        for task_group in tasks:
            if len(task_group) > 1:
                futures: typing.List[
                    concurrent.futures.Future[
                        typing.Union[None, typing.Awaitable[None]]
                    ]
                ] = []
                for task in task_group:
                    futures.append(self._threadpool.submit(curry_context(task), values))
                for future in concurrent.futures.as_completed(futures):
                    exc = future.exception()
                    if exc is not None:
                        raise exc
                    if inspect.isawaitable(future.result()):
                        raise TypeError(
                            "Cannot execute async dependencies in execute_sync"
                        )
            else:
                v = task_group[0](values)
                if inspect.isawaitable(v):
                    raise TypeError("Cannot execute async dependencies in execute_sync")
        return get_result()


class DefaultExecutor(ConcurrentSyncExecutor, ConcurrentAsyncExecutor):
    ...
