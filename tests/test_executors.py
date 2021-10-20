import typing
from typing import Iterable, List, Optional

import pytest

from di.executors import (
    ConcurrentSyncExecutor,
    DefaultExecutor,
    SimpleAsyncExecutor,
    SimpleSyncExecutor,
)
from di.types.executor import SyncExecutor, Task


def make_task() -> Task:
    async def task() -> Iterable[Optional[Task]]:
        return []

    return task


@pytest.mark.parametrize(
    "exc_cls", [DefaultExecutor, SimpleSyncExecutor, ConcurrentSyncExecutor]
)
def test_executing_async_dependencies_in_sync_executor(
    exc_cls: typing.Type[SyncExecutor],
):
    exc = exc_cls()
    match = "Cannot execute async dependencies in execute_sync"
    with pytest.raises(TypeError, match=match):
        exc.execute_sync([make_task()])


def test_simple_sync_executor():
    class Dep:
        called = False

        def __init__(self, deps: List[Optional[Task]]) -> None:
            self.tasks = deps

        def __call__(self) -> Iterable[Optional[Task]]:
            res, self.tasks = self.tasks[:2], self.tasks[2:]
            return res

    exc = SimpleSyncExecutor()

    exc.execute_sync([Dep([Dep([]), Dep([])])])


@pytest.mark.anyio
async def test_simple_async_executor():
    class Dep:
        called = False

        def __init__(self, deps: List[Optional[Task]]) -> None:
            self.tasks = deps

        async def __call__(self) -> Iterable[Optional[Task]]:
            res, self.tasks = self.tasks[:2], self.tasks[2:]
            return res

    exc = SimpleAsyncExecutor()

    await exc.execute_async([Dep([Dep([]), Dep([])])])
