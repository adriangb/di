from __future__ import annotations

from di import Container, Dependant


class Test:
    def __call__(self: Test) -> Test:
        return self


def test_postponed_evaluation_solving():
    container = Container()
    res = container.execute_sync(container.solve(Dependant(Test.__call__)))
    assert isinstance(res, Test)
