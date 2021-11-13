import typing
from typing import Iterable

import pytest

from di.dependant import Dependant
from di.executors import (
    ConcurrentSyncExecutor,
    DefaultExecutor,
    SimpleAsyncExecutor,
    SimpleSyncExecutor,
)
from di.types.executor import AsyncTaskInfo, SyncExecutor, SyncTaskInfo, TaskInfo


@pytest.mark.parametrize(
    "exc_cls", [DefaultExecutor, SimpleSyncExecutor, ConcurrentSyncExecutor]
)
def test_executing_async_dependencies_in_sync_executor(
    exc_cls: typing.Type[SyncExecutor],
):
    async def task() -> Iterable[None]:
        return [None]

    exc = exc_cls()
    match = "Cannot execute async dependencies in execute_sync"
    with pytest.raises(TypeError, match=match):
        exc.execute_sync([AsyncTaskInfo(Dependant(), task)])


def test_simple_sync_executor():
    def task_1() -> Iterable[SyncTaskInfo]:
        return [
            SyncTaskInfo(Dependant(), task_2),
            SyncTaskInfo(Dependant(), task_3),
        ]

    def task_2() -> Iterable[TaskInfo]:
        return []

    def task_3() -> Iterable[None]:
        return [None]

    exc = SimpleSyncExecutor()

    exc.execute_sync([SyncTaskInfo(Dependant(), task_1)])


@pytest.mark.anyio
async def test_simple_async_executor():
    async def task_1() -> Iterable[SyncTaskInfo]:
        return [
            SyncTaskInfo(Dependant(), task_2),
            SyncTaskInfo(Dependant(), task_3),
        ]

    def task_2() -> Iterable[TaskInfo]:
        return []

    def task_3() -> Iterable[None]:
        return [None]

    exc = SimpleAsyncExecutor()

    await exc.execute_async([AsyncTaskInfo(Dependant(), task_1)])
