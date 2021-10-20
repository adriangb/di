from collections import deque
from typing import Deque, Dict, Iterable, List, Mapping, MutableMapping, Set, TypeVar

from di.exceptions import CircularDependencyError

T = TypeVar("T")


def gather_dependants(
    dag: Mapping[T, Iterable[T]],
) -> Mapping[T, Set[T]]:
    dependants: Dict[T, Set[T]] = {k: set() for k in dag}
    for parent in dag.keys():
        for child in dag[parent]:
            dependants[child].add(parent)
    return dependants


def comptue_dependant_counts(
    dag: Mapping[T, Iterable[T]],
) -> MutableMapping[T, int]:
    dependant_count: Dict[T, int] = dict.fromkeys(dag, 0)
    for subdeps in dag.values():
        for subdep in subdeps:
            dependant_count[subdep] += 1
    return dependant_count


def topsort(
    dag: Mapping[T, Iterable[T]],
) -> List[List[T]]:
    """A specialized toplogical sort that:
    1. Groups dependencies so that they can be executed concurrently.
    2. Includes disconnected components of the DAG (i.e. executes the entire DAG).
    """
    groups: List[List[T]] = []
    dependant_count = comptue_dependant_counts(dag)
    q: Deque[T] = deque([node for node in dag.keys() if dependant_count[node] == 0])
    while q:
        group = list(q)
        q.clear()
        for dependant in group:
            for dependency in dag[dependant]:
                try:
                    dependant_count[dependency] -= 1
                except KeyError:
                    raise CircularDependencyError
                if dependant_count[dependency] == 0:
                    dependant_count.pop(dependency)
                    q.append(dependency)
        for dependant in group:
            if dependant_count.pop(dependant, 0) == 0:
                dependant_count.pop(dependant, None)
        groups.append(group)
    for indegree in dependant_count.values():
        if indegree != 0:
            raise CircularDependencyError
    return groups
