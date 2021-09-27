from typing import Any, List

import pytest

from di.container import Container
from di.dependency import Dependant, DependantProtocol, DependencyProvider
from di.params import Depends


def call1():
    ...


def call2(c1: None = Depends(call1)):
    ...


def call3():
    ...


def call4(c2: None = Depends(call2), *, c3: None = Depends(call3)):
    ...


def call5(*, c4: None = Depends(call4)):
    ...


def call6(c4: None = Depends(call4)):
    ...


def call7(c6: None = Depends(call6)):
    ...


def assert_compare_call(
    left: List[DependantProtocol[Any]], right: List[DependencyProvider]
) -> None:
    assert sorted([id(d.call) for d in left]) == sorted([id(call) for call in right])


@pytest.mark.anyio
async def test_get_flat_dependencies():
    container = Container()

    async with container.enter_global_scope("dummy"):
        assert_compare_call(
            container.get_flat_subdependants(container.solve(Dependant(call=call7))),
            [call1, call2, call3, call4, call6],
        )
        assert_compare_call(
            container.get_flat_subdependants(container.solve(Dependant(call=call6))),
            [call1, call2, call3, call4],
        )
        assert_compare_call(
            container.get_flat_subdependants(container.solve(Dependant(call=call5))),
            [call1, call2, call3, call4],
        )
        assert_compare_call(
            container.get_flat_subdependants(container.solve(Dependant(call=call4))),
            [call1, call2, call3],
        )
        assert_compare_call(
            container.get_flat_subdependants(container.solve(Dependant(call=call3))), []
        )
        assert_compare_call(
            container.get_flat_subdependants(container.solve(Dependant(call=call2))),
            [call1],
        )
        assert_compare_call(
            container.get_flat_subdependants(container.solve(Dependant(call=call1))), []
        )
