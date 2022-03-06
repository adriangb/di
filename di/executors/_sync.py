from __future__ import annotations

import inspect

from di.api.executor import State, SyncExecutorProtocol, TaskGraph


class SyncExecutor(SyncExecutorProtocol):
    def execute_sync(self, tasks: TaskGraph, state: State) -> None:
        for task in tasks.static_order():
            maybe_aw = task.compute(state)
            if inspect.isawaitable(maybe_aw):
                raise TypeError("Cannot execute async dependencies in execute_sync")
