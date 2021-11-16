# TODO: remove this test once high-level API is more stable
# This should be tested via public APIs
import typing

import pytest

from di._utils.dag import topsort
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
    ordered = topsort(dag)
    resolved: typing.Set[int] = set()
    for dep in reversed(ordered):
        assert dag[dep].issubset(resolved)
        resolved.add(dep)


@pytest.mark.parametrize("dag", [{0: {0}}, {0: {1}, 1: {0}}, {0: {2}, 1: {2}, 2: {0}}])
def test_cycles(dag: typing.Dict[int, typing.Set[int]]):
    with pytest.raises(CircularDependencyError):
        topsort(dag)


@pytest.mark.parametrize(
    "dag",
    [
        {3: {2}, 2: set(), 1: {0}, 0: set()},
    ],
)
def test_disconnected_deps(dag: typing.Dict[int, typing.Set[int]]):
    """To support sibling dependencies, we want to execute disconnected components as well."""
    ordered = topsort(dag)
    assert set(ordered) == dag.keys()
