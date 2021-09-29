import concurrent.futures
import inspect
import typing

import anyio
import anyio.abc

from di._concurrency import gurantee_awaitable
from di.executor import Executor, Task

ResultType = typing.TypeVar("ResultType")


class ConcurrentSyncExecutor(Executor):
    def __init__(self) -> None:
        self._threadpool = concurrent.futures.ThreadPoolExecutor()

    def execute(
        self,
        tasks: typing.List[typing.Set[Task]],
        get_result: typing.Callable[[], ResultType],
    ) -> ResultType:
        for task_group in tasks:
            if len(task_group) > 1:
                futures: typing.List[
                    concurrent.futures.Future[
                        typing.Union[None, typing.Awaitable[None]]
                    ]
                ] = []
                for task in task_group:
                    futures.append(self._threadpool.submit(task))
                for future in concurrent.futures.as_completed(futures):
                    exc = future.exception()
                    if exc is not None:
                        raise exc
                    if inspect.isawaitable(future.result()):
                        raise TypeError(
                            "Cannot execute async dependencies in a SyncExecutor"
                        )
            else:
                v = next(iter(task_group))()
                if inspect.isawaitable(v):
                    raise TypeError(
                        "Cannot execute async dependencies in a SyncExecutor"
                    )
        return get_result()


class ConcurrentAsyncExecutor(Executor):
    def __init__(self) -> None:
        self._sync_executor = ConcurrentSyncExecutor()

    def execute(
        self,
        tasks: typing.List[typing.Set[Task]],
        get_result: typing.Callable[[], ResultType],
    ) -> typing.Union[ResultType, typing.Awaitable[ResultType]]:
        if any(inspect.iscoroutinefunction(task) for group in tasks for task in group):
            return self._execute_async(tasks, get_result)
        return self._sync_executor.execute(tasks, get_result)

    def _execute_async(
        self,
        tasks: typing.List[typing.Set[Task]],
        get_result: typing.Callable[[], ResultType],
    ) -> typing.Awaitable[ResultType]:
        async def execute() -> ResultType:
            tg: typing.Optional[anyio.abc.TaskGroup] = None
            for task_group in tasks:
                if len(task_group) > 1:
                    if tg is None:
                        tg = anyio.create_task_group()
                    async with tg:
                        for task in task_group:
                            tg.start_soon(gurantee_awaitable(task))  # type: ignore
                else:
                    task = next(iter(task_group))
                    res = task()
                    if res is not None and inspect.isawaitable(res):
                        await res
            return get_result()

        return typing.cast(typing.Awaitable[ResultType], execute())
