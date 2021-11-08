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
    "left,right,hash_eq,eq_qe",
    [
        (Dependant(func), Dependant(func), True, True),
        (Dependant(func, share=False), Dependant(func), True, False),
        (Dependant(func), Dependant(func, share=False), True, False),
        (Dependant(func, share=False), Dependant(func, share=False), True, False),
        (Dependant(func), Custom(func), True, False),
        (Dependant(func), Dependant(other_func), False, False),
    ],
)
def test_equality(
    left: Dependant[Any], right: Dependant[Any], hash_eq: bool, eq_qe: bool
):
    assert (hash(left) == hash(right)) == hash_eq
    assert (left == right) == eq_qe
