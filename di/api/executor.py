from __future__ import annotations

from typing import Iterable, Protocol, Union

from di._task import AsyncTask, ExecutionState, SyncTask

Task = Union[SyncTask, AsyncTask]


class SupportsTaskGraph(Protocol):
    def done(self, task: Task) -> None:
        ...

    def get_ready(self) -> Iterable[Task]:
        ...

    def is_active(self) -> bool:
        ...

    def static_order(self) -> Iterable[Task]:
        ...


class SupportsSyncExecutor(Protocol):
    def execute_sync(self, tasks: SupportsTaskGraph, state: ExecutionState) -> None:
        raise NotImplementedError


class SupportsAsyncExecutor(Protocol):
    async def execute_async(
        self, tasks: SupportsTaskGraph, state: ExecutionState
    ) -> None:
        raise NotImplementedError
