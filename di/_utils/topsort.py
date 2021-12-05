from typing import Dict, Iterable, List, TypeVar

from graphlib2 import TopologicalSorter

T = TypeVar("T")


def topsort(graph: Dict[T, List[T]]) -> Iterable[Iterable[T]]:
    ts = TopologicalSorter(graph)
    ts.prepare()
    result: List[Iterable[T]] = []
    while ts.is_active():
        ready = ts.get_ready()
        result.append(ready)
        ts.done(*ready)
    return result
