from __future__ import annotations

from di import Container
from di.dependent import Dependent
from di.executors import SyncExecutor


class Test:
    def __call__(self: Test) -> Test:
        return self


def test_postponed_evaluation_solving_in_call():
    container = Container()
    with container.enter_scope(None) as state:
        res = container.solve(Dependent(Test.__call__), scopes=[None]).execute_sync(
            executor=SyncExecutor(),
            state=state,
        )
    assert isinstance(res, Test)


class NeedsTest:
    def __init__(self, test: Test) -> None:
        self.test = test


def test_postponed_evaluation_solving_in_init():
    container = Container()
    with container.enter_scope(None) as state:
        res = container.solve(Dependent(NeedsTest), scopes=[None]).execute_sync(
            executor=SyncExecutor(),
            state=state,
        )
    assert isinstance(res, NeedsTest)
