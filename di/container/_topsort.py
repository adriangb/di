from typing import Dict, Iterable, List, TypeVar

from graphlib2 import CycleError, TopologicalSorter

from di.exceptions import DependencyCycleError

T = TypeVar("T")


def topsort(graph: Dict[T, List[T]]) -> Iterable[Iterable[T]]:
    ts = TopologicalSorter(graph)
    try:
        ts.prepare()
    except CycleError as e:
        raise DependencyCycleError(*e.args)
    result: List[Iterable[T]] = []
    while ts.is_active():
        ready = ts.get_ready()
        result.append(ready)
        ts.done(*ready)
    return result
