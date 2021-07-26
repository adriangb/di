from typing import Set

from anydep.container import Container
from anydep.models import Dependant
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


def assert_compare_call(left: Set[Dependant], right: Set[Dependant]) -> None:
    assert {d.call for d in left} == {d.call for d in right}


def test_get_flat_dependencies():
    d1 = Dependant(call1)
    d2 = Dependant(call2)
    d3 = Dependant(call3)
    d4 = Dependant(call4)
    d5 = Dependant(call5)
    d6 = Dependant(call6)
    d7 = Dependant(call7)

    container = Container()

    assert_compare_call(container.get_flat_dependencies(d7), {d1, d2, d3, d4, d6})
    assert_compare_call(container.get_flat_dependencies(d6), {d1, d2, d3, d4})
    assert_compare_call(container.get_flat_dependencies(d5), {d1, d2, d3, d4})
    assert_compare_call(container.get_flat_dependencies(d4), {d1, d2, d3})
    assert_compare_call(container.get_flat_dependencies(d3), set())
    assert_compare_call(container.get_flat_dependencies(d2), {d1})
    assert_compare_call(container.get_flat_dependencies(d1), set())
