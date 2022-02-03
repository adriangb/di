from __future__ import annotations

import inspect
import typing
from collections import deque

import anyio
import anyio.abc

from di._utils.concurrency import callable_in_thread_pool
from di.api.executor import AsyncExecutorProtocol, State, SyncExecutorProtocol, Task

TaskQueue = typing.Deque[typing.Optional[Task]]
TaskResult = typing.Iterable[typing.Union[None, Task]]


class SyncExecutor(SyncExecutorProtocol):
    def __drain(self, queue: TaskQueue, state: State) -> None:
        for task in queue:
            if task is None:
                continue
            if task.is_async:
                raise TypeError("Cannot execute async dependencies in execute_sync")
            task.compute(state)

    def execute_sync(
        self, tasks: typing.Iterable[typing.Optional[Task]], state: State
    ) -> None:
        q: "TaskQueue" = deque(tasks)
        while True:
            task = q.popleft()
            if task is None:
                self.__drain(q, state)
                return
            if task.is_async:
                raise TypeError("Cannot execute async dependencies in execute_sync")
            q.extend(task.compute(state))  # type: ignore[arg-type]  # mypy doesn't recognize task.is_async


class AsyncExecutor(AsyncExecutorProtocol):
    async def __drain(self, queue: TaskQueue, state: State) -> None:
        for task in queue:
            if task is None:
                continue
            res = task.compute(state)
            if inspect.isawaitable(res):
                await res

    async def execute_async(
        self, tasks: typing.Iterable[typing.Optional[Task]], state: State
    ) -> None:
        q: "TaskQueue" = deque(tasks)
        while True:
            task = q.popleft()
            if task is None:
                await self.__drain(q, state)
                return
            if task.is_async:
                res = await task.compute(state)  # type: ignore[assignment,misc]  # mypy doesn't recognize task.is_async
            else:
                res = task.compute(state)
            q.extend(res)  # type: ignore[arg-type]  # mypy doesn't recognize task.is_async


async def _async_worker(
    task: Task,
    state: State,
    taskgroup: anyio.abc.TaskGroup,
) -> None:
    newtasks: "TaskResult"
    if task.is_async:
        newtasks = await task.compute(state)  # type: ignore[assignment,misc]
    else:
        try:
            in_thread = task.dependant.sync_to_thread  # type: ignore[attr-defined]  # allow other Dependant implementations
        except AttributeError:
            in_thread = False
        if in_thread:
            newtasks = await callable_in_thread_pool(task.compute)(state)  # type: ignore[assignment]
        else:
            newtasks = task.compute(state)  # type: ignore[assignment]
    for taskinfo in newtasks:  # type: ignore
        if taskinfo is None:
            continue
        taskgroup.start_soon(_async_worker, taskinfo, state, taskgroup)  # type: ignore  # Pylance doesn't like start_soon


class ConcurrentAsyncExecutor(AsyncExecutorProtocol):
    async def execute_async(
        self, tasks: typing.Iterable[typing.Optional[Task]], state: State
    ) -> None:
        async with anyio.create_task_group() as taskgroup:
            for task in tasks:
                if task is not None:
                    taskgroup.start_soon(_async_worker, task, state, taskgroup)  # type: ignore  # Pylance doesn't like start_soon
