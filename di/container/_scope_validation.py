from typing import Dict, Iterable, Mapping, Sequence

from di.api.providers import DependencyProvider
from di.api.scopes import Scope
from di.container._utils import get_path_str
from di.exceptions import ScopeViolationError, UnknownScopeError


def check_is_inner(
    dep: DependencyProvider,
    subdep: DependencyProvider,
    scope_idxs: Dict[Scope, int],
    parents: Mapping[DependencyProvider, DependencyProvider],
    scopes: Mapping[DependencyProvider, Scope],
) -> None:
    if scope_idxs[scopes[dep]] > scope_idxs[scopes[subdep]]:
        raise ScopeViolationError(
            f"{dep} cannot depend on {subdep} because {subdep}'s"
            f" scope ({scopes[subdep]}) is narrower than {dep}'s scope ({scopes[dep]})"
            f"\nExample Path: {get_path_str(dep, parents)}"
        )


def check_scope(
    dep: DependencyProvider,
    scope_idxs: Dict[Scope, int],
    parents: Mapping[DependencyProvider, DependencyProvider],
    scopes: Mapping[DependencyProvider, Scope],
) -> None:
    if scopes[dep] not in scope_idxs:
        raise UnknownScopeError(
            f"Dependency{dep} has an unknown scope {scopes[dep]}."
            f"\nExample Path: {get_path_str(dep, parents)}"
        )


def validate_scopes(
    scopes: Sequence[Scope],
    dag: Mapping[DependencyProvider, Iterable[DependencyProvider]],
    parents: Mapping[DependencyProvider, DependencyProvider],
    dep_scopes: Mapping[DependencyProvider, Scope],
) -> None:
    """Validate that dependencies all have a valid scope and
    that dependencies only depend on outer scopes or their own scope.
    """
    scope_idxs = {scope: idx for idx, scope in enumerate(reversed(scopes))}
    for dep, predecessors in dag.items():
        check_scope(dep, scope_idxs, parents, dep_scopes)
        for predecessor in predecessors:
            check_scope(predecessor, scope_idxs, parents, dep_scopes)
            check_is_inner(dep, predecessor, scope_idxs, parents, dep_scopes)
