import typing
from typing import Iterable, Optional

import pytest

from di.executors import ConcurrentSyncExecutor, DefaultExecutor, SimpleSyncExecutor
from di.types.executor import SyncExecutor, Task


async def terminal_task() -> Iterable[Optional[Task]]:
    return ()


def make_task(n: int) -> Task:
    async def task() -> Iterable[Optional[Task]]:
        return [terminal_task] * n

    return task


@pytest.mark.parametrize("tasks", [1, 2])
@pytest.mark.parametrize(
    "exc_cls", [DefaultExecutor, SimpleSyncExecutor, ConcurrentSyncExecutor]
)
def test_executing_async_dependencies_in_sync_executor(
    tasks: int, exc_cls: typing.Type[SyncExecutor]
):
    exc = exc_cls()
    match = "Cannot execute async dependencies in execute_sync"
    with pytest.raises(TypeError, match=match):
        exc.execute_sync([make_task(tasks)])


def test_simple_sync_executor():
    class Dep:
        called = False

        def __call__(self) -> None:
            self.called = True

    tasks = [[Dep()], [Dep(), Dep()]]

    exc = SimpleSyncExecutor()

    exc.execute_sync(tasks, lambda: None)  # type: ignore
