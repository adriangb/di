from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Sequence

from di.api.dependencies import DependantBase
from di.api.scopes import Scope
from di.exceptions import ScopeViolationError, UnknownScopeError


def check_is_inner(
    dep: DependantBase[Any],
    subdep: DependantBase[Any],
    scope_idxs: Dict[Scope, int],
) -> None:
    if scope_idxs[dep.scope] > scope_idxs[subdep.scope]:
        raise ScopeViolationError(
            f"{dep} cannot depend on {subdep} because {subdep}'s"
            f" scope ({subdep.scope}) is narrower than {dep}'s scope ({dep.scope})"
        )


def check_scope(dep: DependantBase[Any], scope_idxs: Dict[Scope, int]) -> None:
    if dep.scope not in scope_idxs:
        raise UnknownScopeError(f"Dependency{dep} has an unknown scope {dep.scope}.")


def validate_scopes(
    scopes: Sequence[Scope],
    dag: Mapping[DependantBase[Any], Iterable[DependantBase[Any]]],
) -> None:
    """Validate that dependencies all have a valid scope and
    that dependencies only depend on outer scopes or their own scope.
    """
    scope_idxs = {scope: idx for idx, scope in enumerate(reversed([*scopes, None]))}

    for dep, predecessors in dag.items():
        check_scope(dep, scope_idxs)
        for predecessor in predecessors:
            check_scope(predecessor, scope_idxs)
            check_is_inner(dep, predecessor, scope_idxs)
