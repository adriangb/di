from typing import Any, List, Mapping

from di.api.dependencies import DependantBase


def get_path(
    dep: DependantBase[Any], parents: Mapping[DependantBase[Any], DependantBase[Any]]
) -> List[DependantBase[Any]]:
    path: "List[DependantBase[Any]]" = [dep]
    while dep in parents:
        parent = parents[dep]
        path.append(parent)
        dep = parent
    return list(reversed(path))


def get_path_str(
    dep: DependantBase[Any], parents: Mapping[DependantBase[Any], DependantBase[Any]]
) -> str:
    path = get_path(dep, parents)
    dep_reprs = [repr(d) for d in path]
    dep_reprs[0] += " (root)"
    return " -> ".join(dep_reprs)
