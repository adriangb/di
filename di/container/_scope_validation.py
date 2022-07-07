from typing import Any, Dict, Iterable, Mapping, Sequence

from di.api.dependencies import DependantBase
from di.api.scopes import Scope
from di.container._utils import get_path_str
from di.exceptions import ScopeViolationError, UnknownScopeError


def check_is_inner(
    dep: DependantBase[Any],
    subdep: DependantBase[Any],
    scope_idxs: Dict[Scope, int],
    parents: Mapping[DependantBase[Any], DependantBase[Any]],
) -> None:
    if scope_idxs[dep.scope] > scope_idxs[subdep.scope]:
        raise ScopeViolationError(
            f"{dep} cannot depend on {subdep} because {subdep}'s"
            f" scope ({subdep.scope}) is narrower than {dep}'s scope ({dep.scope})"
            f"\nExample Path: {get_path_str(dep, parents)}"
        )


def check_scope(
    dep: DependantBase[Any],
    scope_idxs: Dict[Scope, int],
    parents: Mapping[DependantBase[Any], DependantBase[Any]],
) -> None:
    if dep.scope not in scope_idxs:
        raise UnknownScopeError(
            f"Dependency{dep} has an unknown scope {dep.scope}."
            f"\nExample Path: {get_path_str(dep, parents)}"
        )


def validate_scopes(
    scopes: Sequence[Scope],
    dag: Mapping[DependantBase[Any], Iterable[DependantBase[Any]]],
    parents: Mapping[DependantBase[Any], DependantBase[Any]],
) -> None:
    """Validate that dependencies all have a valid scope and
    that dependencies only depend on outer scopes or their own scope.
    """
    scope_idxs = {scope: idx for idx, scope in enumerate(reversed(scopes))}
    for dep, predecessors in dag.items():
        check_scope(dep, scope_idxs, parents)
        for predecessor in predecessors:
            check_scope(predecessor, scope_idxs, parents)
            check_is_inner(dep, predecessor, scope_idxs, parents)
