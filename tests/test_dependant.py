from typing import Any, TypeVar

import pytest

from di import Dependant

T = TypeVar("T")


def func() -> None:
    ...


def other_func() -> None:
    ...


class DependantSubclass(Dependant[T]):
    ...


@pytest.mark.parametrize(
    "left,right,hash_eq,eq_qe",
    [
        (Dependant(func), Dependant(func), True, True),
        (Dependant(func, use_cache=False), Dependant(func), False, False),
        (Dependant(func), Dependant(func, use_cache=False), False, False),
        (
            Dependant(func, use_cache=False),
            Dependant(func, use_cache=False),
            False,
            False,
        ),
        (Dependant(func), DependantSubclass(func), False, False),
        (Dependant(func), Dependant(other_func), False, False),
        (Dependant(None), Dependant(None), False, False),
    ],
)
def test_equality(
    left: Dependant[Any], right: Dependant[Any], hash_eq: bool, eq_qe: bool
):
    assert (hash(left.cache_key) == hash(right.cache_key)) == hash_eq
    assert (left.cache_key == right.cache_key) == eq_qe
