import typing

import pytest

from di._topsort import topsort
from di.exceptions import CircularDependencyError


@pytest.mark.parametrize(
    "dag, root",
    [
        ({4: {3}, 3: {0, 1, 2}, 2: {0}, 1: {0}, 0: set()}, 4),
        ({5: {3, 4}, 4: {2}, 3: {2}, 2: {0, 1}, 1: set(), 0: set()}, 5),
        ({3: {1, 2}, 2: set(), 1: {0}, 0: set()}, 3),
    ],
)
def test_topsort(dag: typing.Dict[int, typing.Set[int]], root: int):
    ordered = topsort(root, dag)
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
            topsort(start, dag)
