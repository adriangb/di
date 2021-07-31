from typing import Set

import pytest

from anydep.container import Container
from anydep.models import Dependant, DependencyProvider
from anydep.params import Depends


def call1():
    return


def call2(c1: None = Depends(call1)):
    return


def call3():
    return


def call4(c2: None = Depends(call2), /, *, c3: None = Depends(call3)):
    return


def call5(*, c4: None = Depends(call4)):
    return


def call6(c4: None = Depends(call4)):
    return


def call7(c6: None = Depends(call6)):
    return


def assert_compare_call(left: Set[Dependant], right: Set[DependencyProvider]) -> None:
    assert {d.call for d in left} == right


@pytest.mark.anyio
async def test_get_flat_dependencies():
    container = Container()

    async with container.enter_global_scope("dummy"):
        assert_compare_call(
            container.get_flat_subdependants(Dependant(call=call7)), {call1, call2, call3, call4, call6}
        )
        assert_compare_call(container.get_flat_subdependants(Dependant(call=call6)), {call1, call2, call3, call4})
        assert_compare_call(container.get_flat_subdependants(Dependant(call=call5)), {call1, call2, call3, call4})
        assert_compare_call(container.get_flat_subdependants(Dependant(call=call4)), {call1, call2, call3})
        assert_compare_call(container.get_flat_subdependants(Dependant(call=call3)), set())
        assert_compare_call(container.get_flat_subdependants(Dependant(call=call2)), {call1})
        assert_compare_call(container.get_flat_subdependants(Dependant(call=call1)), set())
