import typing
from typing import Iterable, cast

import pytest

from di.dependant import Dependant
from di.executors import (
    ConcurrentSyncExecutor,
    DefaultExecutor,
    SimpleAsyncExecutor,
    SimpleSyncExecutor,
)
from di.types.dependencies import DependantBase
from di.types.executor import SyncExecutor, SyncTaskReturnValue, Task, TaskInfo


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
        exc.execute_sync([task])


def test_simple_sync_executor():
    def task_1() -> Iterable[TaskInfo]:
        return [
            TaskInfo(Dependant(), task_2),
            TaskInfo(Dependant(), task_3),
        ]

    def task_2() -> Iterable[TaskInfo]:
        return []

    def task_3() -> Iterable[None]:
        return [None]

    exc = SimpleSyncExecutor()

    exc.execute_sync([task_1])


@pytest.mark.anyio
async def test_simple_async_executor():
    async def task_1() -> Iterable[TaskInfo]:
        return [
            TaskInfo(Dependant(), task_2),
            TaskInfo(Dependant(), task_3),
        ]

    def task_2() -> Iterable[TaskInfo]:
        return []

    def task_3() -> Iterable[None]:
        return [None]

    exc = SimpleAsyncExecutor()

    await exc.execute_async([task_1])


def test_accessing_dependant_from_executor():
    class IntrospectingSyncExecutor:
        def execute_sync(self, tasks: typing.Iterable[Task]) -> None:
            q: typing.List[Task] = list(tasks)
            while q:
                task = q.pop(0)
                if task is None:
                    return
                newtasks = cast(SyncTaskReturnValue, task())
                for newtask in newtasks:
                    if newtask is None:
                        return
                    else:
                        q.append(newtask.task)
                        # This is the main assertion in the test!
                        assert isinstance(newtask.dependant, DependantBase)

    def task_1() -> Iterable[TaskInfo]:
        return [TaskInfo(Dependant(), task_2)]

    def task_2() -> Iterable[None]:
        return [None]

    exc = IntrospectingSyncExecutor()

    exc.execute_sync([task_1])
