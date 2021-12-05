import typing
from typing import Any, Iterable, List, Optional

import pytest

from di.api.dependencies import DependantBase
from di.api.executor import AsyncTask, State, SyncExecutor, SyncTask, Task
from di.dependant import Dependant
from di.executors import DefaultExecutor, SimpleAsyncExecutor, SimpleSyncExecutor


class TestAsyncTask(AsyncTask):
    def __init__(
        self,
        dependant: DependantBase[Any],
    ):
        ...

    async def compute(self, state: State) -> Iterable[Optional[Task]]:
        raise NotImplementedError


class TestSyncTask(SyncTask):
    def __init__(
        self,
        dependant: DependantBase[Any],
    ):
        ...

    def compute(self, state: State) -> Iterable[Optional[Task]]:
        raise NotImplementedError


@pytest.mark.parametrize("exc_cls", [DefaultExecutor, SimpleSyncExecutor])
def test_executing_async_dependencies_in_sync_executor(
    exc_cls: typing.Type[SyncExecutor],
):

    state = State(object())
    exc = exc_cls()
    match = "Cannot execute async dependencies in execute_sync"
    with pytest.raises(TypeError, match=match):
        exc.execute_sync([TestAsyncTask(Dependant())], state)


def test_simple_sync_executor():
    executed: List[int] = []

    class Task1(TestSyncTask):
        def compute(self, state: State) -> Iterable[Optional[Task]]:
            executed.append(1)
            return [Task2(Dependant())]

    class Task2(TestSyncTask):
        def compute(self, state: State) -> Iterable[Optional[Task]]:
            executed.append(2)
            return [Task3(Dependant())]

    class Task3(TestSyncTask):
        def compute(self, state: State) -> Iterable[Optional[Task]]:
            executed.append(3)
            return [None]

    exc = SimpleSyncExecutor()

    exc.execute_sync([Task1(Dependant())], State(object()))

    assert executed == [1, 2, 3]


@pytest.mark.anyio
async def test_simple_async_executor():
    executed: List[int] = []

    class Task1(TestAsyncTask):
        async def compute(self, state: State) -> Iterable[Optional[Task]]:
            executed.append(1)
            return [Task2(Dependant())]

    class Task2(TestAsyncTask):
        async def compute(self, state: State) -> Iterable[Optional[Task]]:
            executed.append(2)
            return [Task3(Dependant())]

    class Task3(TestAsyncTask):
        async def compute(self, state: State) -> Iterable[Optional[Task]]:
            executed.append(3)
            return [None]

    exc = SimpleAsyncExecutor()

    await exc.execute_async([Task1(Dependant())], State(object()))

    assert executed == [1, 2, 3]
