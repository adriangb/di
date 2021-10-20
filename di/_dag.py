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
                try:
                    dependant_count[dependency] -= 1
                except KeyError:
                    raise CircularDependencyError
                if dependant_count[dependency] == 0:
                    dependant_count.pop(dependency)
                    q.append(dependency)
        for dependant in level:
            if dependant_count.pop(dependant, 0) == 0:
                dependant_count.pop(dependant, None)
        sorted.extend(level)
    for indegree in dependant_count.values():
        if indegree != 0:
            raise CircularDependencyError
    return sorted
