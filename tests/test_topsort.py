import typing
from collections import defaultdict

import pytest

from di._topsort import topsort
from di.exceptions import CircularDependencyError


@pytest.mark.parametrize(
    "dag",
    [
        {0: set(), 1: {0}, 2: {1}, 3: {0, 2}, 4: {0, 1}, 5: {2, 3}},
        {0: set(), 1: set(), 2: {3}, 3: {1}, 4: {0, 1}, 5: {2, 0}},
    ],
)
def test_topsort(dag: typing.Dict[int, typing.Set[int]]):
    for start in dag:
        ordered = topsort(start, lambda dep: list(dag[dep]), hash=lambda dep: dep)
        resolved: typing.Set[int] = set()
        for group in reversed(ordered):
            for dep in group:
                assert dag[dep].issubset(resolved)
            for dep in group:
                resolved.add(dep)


@pytest.mark.parametrize("dag", [{0: {0}}, {0: {1}, 1: {0}}, {0: {2}, 1: {2}, 2: {0}}])
def test_cycles(dag: typing.Dict[int, typing.Set[int]]):
    for start in dag:
        with pytest.raises(CircularDependencyError):
            topsort(start, lambda dep: list(dag[dep]), hash=lambda dep: dep)


def test_parent_callback():
    dag: typing.Dict[int, typing.Set[int]] = {0: set(), 1: {0}, 2: {1, 0}}
    parents: typing.DefaultDict[int, typing.Set[int]] = defaultdict(set)

    def parent_callback(dep: int, parent: int) -> None:
        parents[dep].add(parent)

    topsort(
        2,
        lambda dep: list(dag[dep]),
        hash=lambda dep: dep,
        parent_callback=parent_callback,
    )
    assert parents == {0: {1, 2}, 1: {2}}
