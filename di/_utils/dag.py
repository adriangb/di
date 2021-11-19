from __future__ import annotations

from collections import deque
from typing import Deque, Dict, Iterable, List, Mapping, MutableMapping, TypeVar

from di.exceptions import CircularDependencyError

T = TypeVar("T")


def comptue_dependant_counts(
    dag: Mapping[T, Iterable[T]],
) -> MutableMapping[T, int]:
    dependant_count: Dict[T, int] = dict.fromkeys(dag, 0)
    for subdeps in dag.values():
        for subdep in subdeps:
            dependant_count[subdep] += 1
    return dependant_count


def topsort(dag: Mapping[T, Iterable[T]]) -> List[T]:
    sorted: List[T] = []
    dependant_count = comptue_dependant_counts(dag)
    q: Deque[T] = deque([node for node in dag.keys() if dependant_count[node] == 0])
    while q:
        level = list(q)
        q.clear()
        for dependant in level:
            for dependency in dag[dependant]:
                dependant_count[dependency] -= 1
                if dependant_count[dependency] == 0:
                    dependant_count.pop(dependency)
                    q.append(dependency)
        for dependant in level:
            if dependant_count.get(dependant, None) == 0:
                dependant_count.pop(dependant, None)
        sorted.extend(level)
    if dependant_count:
        raise CircularDependencyError
    return sorted
