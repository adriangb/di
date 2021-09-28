from typing import Any, TypeVar

import pytest

from di import Dependant

T = TypeVar("T")


def func() -> None:
    ...


def other_func() -> None:
    ...


class Custom(Dependant[T]):
    ...


@pytest.mark.parametrize(
    "d1,d2,hash_eq,eq_qe",
    [
        (Dependant(func), Dependant(func), True, True),
        (Dependant(func, shared=False), Dependant(func), True, False),
        (Dependant(func), Dependant(func, shared=False), True, False),
        (Dependant(func, shared=False), Dependant(func, shared=False), True, False),
        (Dependant(func), Custom(func), True, False),
        (Dependant(func), Dependant(other_func), False, False),
    ],
)
def test_equality(d1: Dependant[Any], d2: Dependant[Any], hash_eq: bool, eq_qe: bool):
    assert (hash(d1) == hash(d2)) == hash_eq
    assert (d1 == d2) == eq_qe
