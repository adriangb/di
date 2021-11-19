from __future__ import annotations

from typing import Any, Collection, Dict

from di.exceptions import ScopeViolationError, UnknownScopeError
from di.types.dependencies import DependantBase
from di.types.scopes import Scope
from di.types.solved import SolvedDependant


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
        raise UnknownScopeError(
            f"Dependency{dep} has an unknown scope {dep.scope}."
            f" Did you forget to enter the {dep.scope} scope?"
        )


def validate_scopes(scopes: Collection[Scope], solved: SolvedDependant[Any]) -> None:
    """Validate that dependencies all have a valid scope and
    that dependencies only depend on outer scopes or their own scope.
    """
    scope_idxs = {scope: idx for idx, scope in enumerate(reversed([*scopes, None]))}

    for dep, params in solved.dag.items():
        check_scope(dep, scope_idxs)
        for param in params:
            subdep = param.dependency
            check_scope(subdep, scope_idxs)
            check_is_inner(dep, subdep, scope_idxs)
