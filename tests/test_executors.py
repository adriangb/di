import typing
from typing import Iterable, Optional

import pytest

from di.dependant import Dependant
from di.executors import DefaultExecutor, SimpleAsyncExecutor, SimpleSyncExecutor
from di.types.executor import AsyncTaskInfo, SyncExecutor, SyncTaskInfo, TaskInfo


@pytest.mark.parametrize("exc_cls", [DefaultExecutor, SimpleSyncExecutor])
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
    executed: set[int] = set()

    def task_1() -> Iterable[Optional[TaskInfo]]:
        executed.add(1)
        return [
            SyncTaskInfo(Dependant(), task_2),
        ]

    def task_2() -> Iterable[Optional[TaskInfo]]:
        executed.add(2)
        return [SyncTaskInfo(Dependant(), task_3), None]

    def task_3() -> Iterable[Optional[TaskInfo]]:
        executed.add(3)
        return []

    exc = SimpleSyncExecutor()

    exc.execute_sync([SyncTaskInfo(Dependant(), task_1)])

    assert executed == {1, 2, 3}


@pytest.mark.anyio
async def test_simple_async_executor():
    executed: set[int] = set()

    async def task_1() -> Iterable[Optional[TaskInfo]]:
        executed.add(1)
        return [
            AsyncTaskInfo(Dependant(), task_2),
        ]

    async def task_2() -> Iterable[Optional[TaskInfo]]:
        executed.add(2)
        return [SyncTaskInfo(Dependant(), task_3), None]

    def task_3() -> Iterable[Optional[TaskInfo]]:
        executed.add(3)
        return []

    exc = SimpleAsyncExecutor()

    await exc.execute_async([AsyncTaskInfo(Dependant(), task_1)])

    assert executed == {1, 2, 3}
