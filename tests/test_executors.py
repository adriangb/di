from typing import Any, Iterable, List, Optional

import pytest

from di.api.dependencies import DependantBase
from di.api.executor import Task
from di.dependant import Dependant
from di.executors import AsyncExecutor, SyncExecutor


class TestAsyncTask(Task):
    def __init__(
        self,
        dependant: DependantBase[Any],
    ):
        ...

    async def compute(self, state: Any) -> Iterable[Optional[Task]]:
        raise NotImplementedError


class TestSyncTask(Task):
    def __init__(
        self,
        dependant: DependantBase[Any],
    ):
        ...

    def compute(self, state: Any) -> Iterable[Optional[Task]]:
        raise NotImplementedError


def test_executing_async_dependencies_in_sync_executor():

    state = object()
    exc = SyncExecutor()
    match = "Cannot execute async dependencies in execute_sync"
    with pytest.raises(TypeError, match=match):
        exc.execute_sync([TestAsyncTask(Dependant())], state)


def test_simple_sync_executor():
    executed: List[int] = []

    class Task1(TestSyncTask):
        def compute(self, state: Any) -> Iterable[Optional[Task]]:
            executed.append(1)
            return [Task2(Dependant())]

    class Task2(TestSyncTask):
        def compute(self, state: Any) -> Iterable[Optional[Task]]:
            executed.append(2)
            return [Task3(Dependant())]

    class Task3(TestSyncTask):
        def compute(self, state: Any) -> Iterable[Optional[Task]]:
            executed.append(3)
            return [None]

    exc = SyncExecutor()

    exc.execute_sync([Task1(Dependant())], object())

    assert executed == [1, 2, 3]


@pytest.mark.anyio
async def test_simple_async_executor():
    executed: List[int] = []

    class Task1(TestAsyncTask):
        async def compute(self, state: Any) -> Iterable[Optional[Task]]:
            executed.append(1)
            return [Task2(Dependant())]

    class Task2(TestAsyncTask):
        async def compute(self, state: Any) -> Iterable[Optional[Task]]:
            executed.append(2)
            return [Task3(Dependant())]

    class Task3(TestAsyncTask):
        async def compute(self, state: Any) -> Iterable[Optional[Task]]:
            executed.append(3)
            return [None]

    exc = AsyncExecutor()

    await exc.execute_async([Task1(Dependant())], object())

    assert executed == [1, 2, 3]
