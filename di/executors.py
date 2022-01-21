from __future__ import annotations

import inspect
import typing
from collections import deque

import anyio
import anyio.abc

from di._utils.concurrency import callable_in_thread_pool
from di.api.executor import AsyncExecutorProtocol, SyncExecutorProtocol, Task

TaskQueue = typing.Deque[typing.Optional[Task]]
TaskResult = typing.Iterable[typing.Union[None, Task]]


class SyncExecutor(SyncExecutorProtocol):
    def __drain(self, queue: TaskQueue, state: typing.Any) -> None:
        for task in queue:
            if task is None:
                continue
            res = task.compute(state)
            if inspect.isawaitable(res):
                raise TypeError("Cannot execute async dependencies in execute_sync")
            task.compute(state)

    def execute_sync(
        self, tasks: typing.Iterable[typing.Optional[Task]], state: typing.Any
    ) -> None:
        q: "TaskQueue" = deque(tasks)
        while True:
            task = q.popleft()
            if task is None:
                self.__drain(q, state)
                return
            res = task.compute(state)
            if inspect.isawaitable(res):
                raise TypeError("Cannot execute async dependencies in execute_sync")
            q.extend(res)  # type: ignore[arg-type]  # mypy doesn't recognize inspect.isawaitable


class AsyncExecutor(AsyncExecutorProtocol):
    async def __drain(self, queue: TaskQueue, state: typing.Any) -> None:
        for task in queue:
            if task is None:
                continue
            res = task.compute(state)
            if inspect.isawaitable(res):
                await res

    async def execute_async(
        self, tasks: typing.Iterable[typing.Optional[Task]], state: typing.Any
    ) -> None:
        q: "TaskQueue" = deque(tasks)
        while True:
            task = q.popleft()
            if task is None:
                await self.__drain(q, state)
                return
            res = task.compute(state)
            if inspect.isawaitable(res):
                res = await res
            q.extend(res)  # type: ignore[arg-type]  # mypy doesn't recognize inspect.isawaitable


async def _async_worker(
    task: Task,
    state: typing.Any,
    taskgroup: anyio.abc.TaskGroup,
) -> None:
    if (
        getattr(task.dependant, "sync_to_thread", False) is True
    ):  # instance of Dependant
        newtasks = await callable_in_thread_pool(task.compute)(state)
    else:
        newtasks = task.compute(state)
        if inspect.isawaitable(newtasks):
            newtasks = await newtasks
    for taskinfo in typing.cast(TaskResult, newtasks):
        if taskinfo is None:
            continue
        taskgroup.start_soon(_async_worker, taskinfo, state, taskgroup)


class ConcurrentAsyncExecutor(AsyncExecutorProtocol):
    async def execute_async(
        self, tasks: typing.Iterable[typing.Optional[Task]], state: typing.Any
    ) -> None:
        async with anyio.create_task_group() as taskgroup:
            for task in tasks:
                if task is not None:
                    taskgroup.start_soon(_async_worker, task, state, taskgroup)
