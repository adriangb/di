from typing import Any, List

import pytest

from di import Container, Dependant, Marker
from di.api.dependencies import DependantBase
from di.api.providers import DependencyProvider
from di.typing import Annotated


def call1():
    ...


def call2(c1: Annotated[None, Marker(call1)]):
    ...


def call3():
    ...


def call4(c2: Annotated[None, Marker(call2)], *, c3: Annotated[None, Marker(call3)]):
    ...


def call5(*, c4: Annotated[None, Marker(call4)]):
    ...


def call6(c4: Annotated[None, Marker(call4)]):
    ...


def call7(c6: Annotated[None, Marker(call6)]):
    ...


def assert_compare_call(
    left: List[DependantBase[Any]], right: List[DependencyProvider]
) -> None:
    assert sorted([id(d.call) for d in left]) == sorted([id(call) for call in right])


@pytest.mark.anyio
async def test_get_flat_dependencies():
    container = Container()

    assert_compare_call(
        container.solve(Dependant(call=call7)).get_flat_subdependants(),
        [call1, call2, call3, call4, call6],
    )
    assert_compare_call(
        container.solve(Dependant(call=call6)).get_flat_subdependants(),
        [call1, call2, call3, call4],
    )
    assert_compare_call(
        container.solve(Dependant(call=call5)).get_flat_subdependants(),
        [call1, call2, call3, call4],
    )
    assert_compare_call(
        container.solve(Dependant(call=call4)).get_flat_subdependants(),
        [call1, call2, call3],
    )
    assert_compare_call(
        container.solve(Dependant(call=call3)).get_flat_subdependants(), []
    )
    assert_compare_call(
        container.solve(Dependant(call=call2)).get_flat_subdependants(),
        [call1],
    )
    assert_compare_call(
        container.solve(Dependant(call=call1)).get_flat_subdependants(), []
    )
