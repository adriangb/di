from __future__ import annotations

from di import Container, Dependant, SyncExecutor


class Test:
    def __call__(self: Test) -> Test:
        return self


def test_postponed_evaluation_solving():
    container = Container()
    with container.enter_scope(None) as state:
        res = container.execute_sync(
            container.solve(Dependant(Test.__call__), scopes=[None]),
            executor=SyncExecutor(),
            state=state,
        )
    assert isinstance(res, Test)
