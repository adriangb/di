from __future__ import annotations

import pytest

from di import Container, Dependant


class Test:
    def __call__(self: Test) -> Test:
        return self


@pytest.mark.anyio
async def test_postponed_evaluation_solving():
    container = Container()
    res = await container.execute(Dependant(Test.__call__))
    assert isinstance(res, Test)
