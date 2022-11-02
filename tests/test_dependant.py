from typing import Any, TypeVar

import pytest

from di.dependent import Dependent

T = TypeVar("T")


def func() -> None:
    ...


def other_func() -> None:
    ...


class DependentSubclass(Dependent[T]):
    ...


@pytest.mark.parametrize(
    "left,right,hash_eq,eq_qe",
    [
        (Dependent(func), Dependent(func), True, True),
        (Dependent(func, use_cache=False), Dependent(func), False, False),
        (Dependent(func), Dependent(func, use_cache=False), False, False),
        (
            Dependent(func, use_cache=False),
            Dependent(func, use_cache=False),
            False,
            False,
        ),
        (Dependent(func), DependentSubclass(func), False, False),
        (Dependent(func), Dependent(other_func), False, False),
        (Dependent(None), Dependent(None), False, False),
    ],
)
def test_equality(
    left: Dependent[Any], right: Dependent[Any], hash_eq: bool, eq_qe: bool
):
    assert (hash(left.cache_key) == hash(right.cache_key)) == hash_eq
    assert (left.cache_key == right.cache_key) == eq_qe
