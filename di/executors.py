from __future__ import annotations

import typing
from collections import deque

import anyio
import anyio.abc

from di._utils.concurrency import callable_in_thread_pool
from di.api.executor import (
    AsyncExecutorProtocol,
    AsyncTask,
    State,
    SyncExecutorProtocol,
    Task,
)

TaskQueue = typing.Deque[typing.Optional[Task]]


class SyncExecutor(SyncExecutorProtocol):
    def __drain(self, queue: TaskQueue, state: State) -> None:
        for task in queue:
            if task is None:
                continue
            if isinstance(task, AsyncTask):
                raise TypeError("Cannot execute async dependencies in execute_sync")
            task.compute(state)

    def execute_sync(
        self, tasks: typing.Iterable[typing.Optional[Task]], state: State
    ) -> None:
        q: TaskQueue = deque(tasks)
        while True:
            task = q.popleft()
            if task is None:
                self.__drain(q, state)
                return
            if isinstance(task, AsyncTask):
                raise TypeError("Cannot execute async dependencies in execute_sync")
            q.extend(task.compute(state))


class AsyncExecutor(AsyncExecutorProtocol):
    async def __drain(self, queue: TaskQueue, state: State) -> None:
        for task in queue:
            if task is None:
                continue
            if isinstance(task, AsyncTask):
                await task.compute(state)
            else:
                task.compute(state)
            task.compute(state)

    async def execute_async(
        self, tasks: typing.Iterable[typing.Optional[Task]], state: State
    ) -> None:
        q: TaskQueue = deque(tasks)
        while True:
            task = q.popleft()
            if task is None:
                await self.__drain(q, state)
                return
            if isinstance(task, AsyncTask):
                newtasks = await task.compute(state)
            else:
                newtasks = task.compute(state)
            q.extend(newtasks)


async def _async_worker(
    task: Task,
    state: State,
    taskgroup: anyio.abc.TaskGroup,
) -> None:
    if isinstance(task, AsyncTask):
        newtasks = await task.compute(state)
    elif (
        getattr(task.dependant, "sync_to_thread", False) is True
    ):  # instance of Dependant
        newtasks = await callable_in_thread_pool(task.compute)(state)
    else:
        newtasks = task.compute(state)
    for taskinfo in newtasks:
        if taskinfo is None:
            continue
        taskgroup.start_soon(_async_worker, taskinfo, state, taskgroup)


class ConcurrentAsyncExecutor(AsyncExecutorProtocol):
    async def execute_async(
        self, tasks: typing.Iterable[typing.Optional[Task]], state: State
    ) -> None:
        async with anyio.create_task_group() as taskgroup:
            for task in tasks:
                if task is not None:
                    taskgroup.start_soon(_async_worker, task, state, taskgroup)
