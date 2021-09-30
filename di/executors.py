import concurrent.futures
import inspect
import typing

import anyio
import anyio.abc

from di._concurrency import curry_context, gurantee_awaitable
from di.types.executor import AsyncExecutor, SyncExecutor, Task

ResultType = typing.TypeVar("ResultType")
T = typing.TypeVar("T")


def _all_sync(tasks: typing.Collection[Task]) -> bool:
    return not any(inspect.iscoroutinefunction(task) for task in tasks)


class DefaultExecutor(AsyncExecutor, SyncExecutor):
    def __init__(self) -> None:
        self._threadpool = concurrent.futures.ThreadPoolExecutor()

    def execute_sync(
        self,
        tasks: typing.List[typing.Collection[Task]],
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
                    futures.append(self._threadpool.submit(curry_context(task)))
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

    async def execute_async(
        self,
        tasks: typing.List[typing.Collection[Task]],
        get_result: typing.Callable[[], ResultType],
    ) -> ResultType:
        tg: typing.Optional[anyio.abc.TaskGroup] = None
        for task_group in tasks:
            if len(task_group) > 1:
                if _all_sync(task_group):
                    self.execute_sync([task_group], lambda: None)
                else:
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
