from __future__ import annotations

import typing
from collections import deque

import anyio
import anyio.abc

from di._utils.concurrency import callable_in_thread_pool
from di.api.executor import AsyncExecutor, AsyncTaskInfo, SyncExecutor, TaskInfo

TaskQueue = typing.Deque[TaskInfo]


class SimpleSyncExecutor(SyncExecutor):
    def execute_sync(self, tasks: typing.Iterable[TaskInfo]) -> None:
        q: TaskQueue = deque(tasks)
        while True:
            task = q.popleft()
            if isinstance(task, AsyncTaskInfo):
                raise TypeError("Cannot execute async dependencies in execute_sync")
            newtasks = task.task()
            for newtask in newtasks:
                if newtask is None:
                    for task in q:
                        if isinstance(task, AsyncTaskInfo):
                            raise TypeError(
                                "Cannot execute async dependencies in execute_sync"
                            )
                        task.task()
                    return
                else:
                    q.append(newtask)


class SimpleAsyncExecutor(AsyncExecutor):
    async def execute_async(self, tasks: typing.Iterable[TaskInfo]) -> None:
        q: TaskQueue = deque(tasks)
        while True:
            task = q.popleft()
            if isinstance(task, AsyncTaskInfo):
                newtasks = await task.task()
            else:
                newtasks = task.task()
            for newtask in newtasks:
                if newtask is None:
                    for task in q:
                        if isinstance(task, AsyncTaskInfo):
                            newtasks = await task.task()
                        else:
                            newtasks = task.task()
                    return
                else:
                    q.append(newtask)


async def _async_worker(
    task: TaskInfo,
    taskgroup: anyio.abc.TaskGroup,
) -> None:
    if isinstance(task, AsyncTaskInfo):
        newtasks = await task.task()
    elif (
        getattr(task.dependant, "sync_to_thread", False) is True
    ):  # instance of Dependant
        newtasks = await callable_in_thread_pool(task.task)()
    else:
        newtasks = task.task()
    for taskinfo in newtasks:
        if taskinfo is None:
            continue
        taskgroup.start_soon(_async_worker, taskinfo, taskgroup)


class ConcurrentAsyncExecutor(AsyncExecutor):
    async def execute_async(self, tasks: typing.Iterable[TaskInfo]) -> None:
        async with anyio.create_task_group() as taskgroup:
            for task in tasks:
                taskgroup.start_soon(_async_worker, task, taskgroup)


class DefaultExecutor(ConcurrentAsyncExecutor, SimpleSyncExecutor):
    pass
