from __future__ import annotations

import itertools
from typing import Any, Collection, Dict, Generator, Hashable, Iterable, Sequence, Set, TypeVar
import sys
if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

import pytest

from di._utils.topsort import TopologicalSorter, CycleError
# from graphlib import TopologicalSorter, CycleError


class Node(Hashable, Protocol):
    """Nodes need comparable to be sorted for determinsm in tests"""
    def __lt__(self, __other: Any) -> bool: ...
    def __hash__(self) -> int: ...
    def __eq__(self, o: object) -> bool: ...


T = TypeVar("T", bound=Node)


def cycles_match(c1: Iterable[T], c2: Iterable[T]) -> bool:
    c1, c2 = list(c1), list(c2)
    # the first and last element in a cycle is the same
    # but since the cycle could start anywhere
    # there may not be the same elements in each
    assert c1[0] == c1[-1]
    c1.pop()
    assert c2[0] == c2[-1]
    c2.pop()
    # now we should have exactly the same elements, but possibly not
    # in the same order
    s1 = " ".join([str(x) for x in c1])
    s2 = " ".join([str(x) for x in c2] * 2)
    return s1 in s2


def get_static_order_from_groups(ts: TopologicalSorter[T]) -> Generator[Set[T], None, None]:
    while ts.is_active():
        nodes = ts.get_ready()
        for node in nodes:
            ts.done(node)
        yield set(sorted(nodes))


def assert_expected_resolution(
    graph: Dict[T, Iterable[T]],
    expected: Iterable[Collection[T]]
):
    ts = TopologicalSorter(graph)
    ts.prepare()
    assert list(get_static_order_from_groups(ts)) == [set(e) for e in expected]

    ts = TopologicalSorter(graph)
    group_iterator = iter(ts.static_order())
    for group in expected:
        got = itertools.islice(group_iterator, len(group))
        assert set(got) == set(group)


def assert_cycles(
    graph: Dict[T, Sequence[T]],
    cycles: Iterable[Sequence[T]],
):
    ts: TopologicalSorter[T] = TopologicalSorter()
    for node, pred in graph.items():
        ts.add(node, *pred)
    try:
        ts.prepare()
    except CycleError as e:
        _, seq = e.args
        for cycle in cycles:
            if cycles_match(cycle, seq):
                return
        raise AssertionError(
            f"Cycles did not match: {cycles} does not contain {seq}"
        )
    else:
        raise AssertionError("CycleError was not raised")



@pytest.mark.parametrize(
    "graph,expected", [
        (
            {2: {11}, 9: {11, 8}, 10: {11, 3}, 11: {7, 5}, 8: {7, 3}},
            [(3, 5, 7), (8, 11), (2, 9, 10)],
        ),
        ({1: {}}, [(1,)]),
        ({x: {x + 1} for x in range(10)}, [(x,) for x in range(10, -1, -1)]),
        ({2: {3}, 3: {4}, 4: {5}, 5: {1}, 11: {12}, 12: {13}, 13: {14}, 14: {15}}, [(1, 15), (5, 14), (4, 13), (3, 12), (2, 11)]),
        (
            {
                0: [1, 2],
                1: [3],
                2: [5, 6],
                3: [4],
                4: [9],
                5: [3],
                6: [7],
                7: [8],
                8: [4],
                9: [],
            },
            [(9,), (4,), (3, 8), (1, 5, 7), (6,), (2,), (0,)],
        ),
        ({0: [1, 2], 1: [], 2: [3], 3: []}, [(1, 3), (2,), (0,)]),
        (
            {0: [1, 2], 1: [], 2: [3], 3: [], 4: [5], 5: [6], 6: []},
            [(1, 3, 6), (2, 5), (0, 4)],
        ),
    ]
)
def test_simple_cases(
    graph: Dict[int, Iterable[int]],
    expected: Iterable[Collection[int]],
):
    assert_expected_resolution(graph, expected)

@pytest.mark.parametrize(
    "graph,expected", [
        ({1: {2}, 3: {4}, 5: {6}}, [(2, 4, 6), (1, 3, 5)]),
        ({1: set(), 3: set(), 5: set()}, [(1, 3, 5)]),
    ]
)
def test_no_dependencies(
    graph: Dict[int, Iterable[int]],
    expected: Iterable[Collection[int]],
):
    assert_expected_resolution(graph, expected)


def test_node_repeated_in_dependencies():
    # Test same node multiple times in dependencies
    assert_expected_resolution(
        {0: [2, 4, 4, 4, 4, 4], 1: {2}, 3: {4}},
        [(2, 4), (0, 1, 3)]
    )

    # Test adding the same dependency multiple times
    ts: TopologicalSorter[int] = TopologicalSorter()
    ts.add(1, 2)
    ts.add(1, 2)
    ts.add(1, 2)
    assert list(ts.static_order()) == [2, 1]


def test_graph_with_iterables():
    dependson = (2 * x + 1 for x in range(5))
    graph = {0: dependson}
    ts = TopologicalSorter(graph)
    expected = {1, 3, 5, 7, 9}
    it = iter(ts.static_order())
    assert set(itertools.islice(it, len(expected))) == expected
    assert next(it) == 0


def test_add_dependencies_for_same_node_incrementally():
    graph = {1: {2, 3, 4, 5}}
    # Test same node multiple times
    ts: TopologicalSorter[int] = TopologicalSorter()
    for k, vs in graph.items():
        for v in vs:
            ts.add(k, v)

    ts2 = TopologicalSorter(graph)
    res1, res2 = list(ts.static_order()), list(ts2.static_order())
    # our root (1) should be last, all others should be the same
    assert res1.pop() == res2.pop()
    assert set(res1) == set(res2)


def test_empty():
    assert_expected_resolution({}, [])


@pytest.mark.parametrize(
    "graph,cycles", [
        ({1: {1}}, [[1, 1]]),
        ({1: {2}, 2: {1}}, [[1, 2, 1]]),
        ({1: {2}, 2: {3}, 3: {1}}, [[1, 3, 2, 1]]),
        ({1: {2}, 2: {3}, 3: {1}, 5: {4}, 4: {6}}, [[1, 3, 2, 1]]),
        ({1: {2}, 2: {1}, 3: {4}, 4: {5}, 6: {7}, 7: {6}}, [[1, 2, 1], [7, 6, 7]]),
        ({1: {2}, 2: {3}, 3: {2, 4}, 4: {5}}, [[3, 2, 3]]),
    ],
    ids=[
        "self cycle",
        "simple cycle",
        "indirect cycle",
        "not all elements involved in a cycle",
        "multiple cycles",
        "cycle in the middle of the graph",
    ]
)
def test_cycle(
    graph: Dict[int, Sequence[int]],
    cycles: Iterable[Sequence[int]],
):
    assert_cycles(graph, cycles)
 

def test_calls_before_prepare():
    ts: TopologicalSorter[int] = TopologicalSorter()

    with pytest.raises(ValueError, match=r"prepare\(\) must be called first"):
        ts.get_ready()
    with pytest.raises(ValueError, match=r"prepare\(\) must be called first"):
        ts.done(3)
    with pytest.raises(ValueError, match=r"prepare\(\) must be called first"):
        ts.is_active()


def test_prepare_multiple_times():
    ts: TopologicalSorter[Node] = TopologicalSorter()
    ts.prepare()
    with pytest.raises(ValueError, match=r"cannot prepare\(\) more than once"):
        ts.prepare()


def test_invalid_nodes_in_done():
    ts: TopologicalSorter[int] = TopologicalSorter()
    ts.add(1, 2, 3, 4)
    ts.add(2, 3, 4)
    ts.prepare()
    ts.get_ready()

    with pytest.raises(ValueError, match="node 2 was not passed out"):
        ts.done(2)
    with pytest.raises(ValueError, match=r"node 24 was not added using add\(\)"):
        ts.done(24)

def test_done():
    ts: TopologicalSorter[int] = TopologicalSorter()
    ts.add(1, 2, 3, 4)
    ts.add(2, 3)
    ts.prepare()

    assert set(ts.get_ready()) == {3, 4}
    # If we don't mark anything as done, get_ready() returns nothing
    assert set(ts.get_ready()) == set()
    ts.done(3)
    # Now 2 becomes available as 3 is done
    assert set(ts.get_ready()) == {2}
    assert set(ts.get_ready()) == set()
    ts.done(4)
    ts.done(2)
    # Only 1 is missing
    assert set(ts.get_ready()) == {1}
    assert set(ts.get_ready()) == set()
    ts.done(1)
    assert set(ts.get_ready()) == set()
    assert not set(ts.get_ready())

def test_is_active():
    ts: TopologicalSorter[int] = TopologicalSorter()
    ts.add(1, 2)
    ts.prepare()

    assert ts.is_active()
    assert ts.get_ready() == (2,)
    assert ts.is_active()
    ts.done(2)
    assert ts.is_active()
    assert ts.get_ready() == (1,)
    assert ts.is_active()
    ts.done(1)
    assert not ts.is_active()


def test_not_hashable_nodes():
    ts: TopologicalSorter[Any] = TopologicalSorter()
    with pytest.raises(TypeError):
        ts.add(dict(), 1)
    with pytest.raises(TypeError):
        ts.add(1, dict())
    with pytest.raises(TypeError):
        ts.add(dict(), 1)


def test_order_of_insertion_does_not_matter_between_groups():
    def get_groups(ts: TopologicalSorter[int]) -> Generator[Set[int], None, None]:
        ts.prepare()
        while ts.is_active():
            nodes = ts.get_ready()
            ts.done(*nodes)
            yield set(nodes)

    ts: TopologicalSorter[int] = TopologicalSorter()
    ts.add(3, 2, 1)
    ts.add(1, 0)
    ts.add(4, 5)
    ts.add(6, 7)
    ts.add(4, 7)

    ts2: TopologicalSorter[int] = TopologicalSorter()
    ts2.add(1, 0)
    ts2.add(3, 2, 1)
    ts2.add(4, 7)
    ts2.add(6, 7)
    ts2.add(4, 5)

    assert list(get_groups(ts)) == list(get_groups(ts2))


def test_execute_after_copy():
    graph = {0: [1]}
    ts = TopologicalSorter(graph)
    ts.prepare()
    ts2 = ts.copy()

    assert list(get_static_order_from_groups(ts)) == [{1}, {0}]
    assert not ts.is_active()

    assert list(get_static_order_from_groups(ts2)) == [{1}, {0}]
    assert not ts2.is_active()
