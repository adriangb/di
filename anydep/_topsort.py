from collections import defaultdict
from typing import (
    Callable,
    DefaultDict,
    Dict,
    List,
    Optional,
    Protocol,
    Set,
    Tuple,
    TypeVar,
)

from anydep.exceptions import CircularDependencyError

T = TypeVar("T")
T_contra = TypeVar("T_contra", contravariant=True)


class ParentCallback(Protocol[T_contra]):
    def __call__(self, dep: T_contra, parent: T_contra) -> None:
        ...


def topsort(
    dependency: T,
    gather_sub_dependants: Callable[[T], List[T]],
    hash: Callable[[T], int],
    parent_callback: Optional[ParentCallback[T]] = None,
) -> List[List[T]]:
    """Topological sort with grouping.

    The base function accepts parameters for gathering sub dependencies and hasing (identifying) dependencies
    such that the same algorithm can be used for a DAG of integers as well as more complex types simply by
    changing the semantics of a hash or how sub dependencies are gathered.

    Note that we use recursive DFS solution here because we don't have an a priori list of all dependencies.
    Otherwise, Kahn's or other solutions could be used.

    Additionally, we do not assume that each dependency has a unique hash, instead we force hashing
    to go through the `hash` parameter so that the semantics can be easily changed.
    """

    order: Dict[int, Tuple[int, T]] = {hash(dependency): (0, dependency)}

    def util(dep: T, visited: Set[int], level: int, parent: Optional[T]):
        dep_hash = hash(dep)
        if dep_hash in visited:
            raise CircularDependencyError("Found a cycle!")
        visited = visited | {dep_hash}
        if parent_callback is not None and parent is not None:
            parent_callback(dep, parent)
        for subdep in gather_sub_dependants(dep):
            util(subdep, visited, level + 1, dep)
        order[dep_hash] = (max(order.get(dep_hash, (-1, dep))[0], level), dep)

    util(dependency, set(), 0, None)
    res: DefaultDict[int, List[T]] = defaultdict(list)
    for val in sorted(order.values(), key=lambda v: v[0]):
        res[val[0]].append(val[1])
    return list(res.values())
