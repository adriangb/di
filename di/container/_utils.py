from typing import List, Mapping, TypeVar

T = TypeVar("T")


def get_path(dep: T, parents: Mapping[T, T]) -> List[T]:
    path: "List[T]" = [dep]
    while dep in parents:
        parent = parents[dep]
        path.append(parent)
        dep = parent
    return list(reversed(path))


def get_path_str(dep: T, parents: Mapping[T, T]) -> str:
    path = get_path(dep, parents)
    dep_reprs = [repr(d) for d in path]
    dep_reprs[0] += " (root)"
    return " -> ".join(dep_reprs)
