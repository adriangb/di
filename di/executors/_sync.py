from __future__ import annotations

import typing
from collections import deque

from di.api.executor import State, SyncExecutorProtocol, Task

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
