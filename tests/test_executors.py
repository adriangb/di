import typing
from typing import Awaitable, Callable, List

import pytest

from di.executors import ConcurrentSyncExecutor, DefaultExecutor, SimpleSyncExecutor
from di.types.executor import SyncExecutor, Values


async def task(values: Values) -> None:
    ...


@pytest.mark.parametrize("tasks", [[[task]], [[task, task]]])
@pytest.mark.parametrize(
    "exc_cls", [DefaultExecutor, SimpleSyncExecutor, ConcurrentSyncExecutor]
)
def test_executing_async_dependencies_in_sync_executor(
    tasks: List[List[Callable[[], Awaitable[None]]]], exc_cls: typing.Type[SyncExecutor]
):
    exc = exc_cls()
    with pytest.raises(
        TypeError, match="Cannot execute async dependencies in execute_sync"
    ):
        exc.execute_sync(tasks, lambda: None, {})  # type: ignore


def test_simple_sync_executor():
    class Dep:
        called = False

        def __call__(self, values: Values) -> None:
            self.called = True

    tasks = [[Dep()], [Dep(), Dep()]]

    exc = SimpleSyncExecutor()

    exc.execute_sync(tasks, lambda: None, {})
