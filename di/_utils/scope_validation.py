from __future__ import annotations

from functools import lru_cache
from typing import Any, Collection, Dict, Tuple

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


# Validating scopes is relatively expensive since we need to iterate over the DAG
# But it is easily cacheable:
# For a given sequence of scopes and solved dependant the result is always the same
# So we trade off memory for performance
@lru_cache(maxsize=2 ** 8)
def _validate_scopes(scopes: Tuple[Scope, ...], solved: SolvedDependant[Any]) -> None:
    scope_idxs = {scope: idx for idx, scope in enumerate(reversed([*scopes, None]))}

    for dep, params in solved.dag.items():
        check_scope(dep, scope_idxs)
        for param in params:
            subdep = param.dependency
            check_scope(subdep, scope_idxs)
            check_is_inner(dep, subdep, scope_idxs)


def validate_scopes(scopes: Collection[Scope], solved: SolvedDependant[Any]) -> None:
    """Validate that dependencies all have a valid scope and
    that dependencies only depend on outer scopes or their own scope.
    """
    return _validate_scopes(tuple(scopes), solved)
