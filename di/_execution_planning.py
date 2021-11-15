from collections import deque
from typing import (
    Any,
    Deque,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Set,
    Tuple,
)

from di import _scope_validation as scope_validation
from di._state import ContainerState
from di._task import ExecutionState, Task
from di.types.dependencies import DependantBase
from di.types.executor import TaskInfo
from di.types.providers import DependencyProvider
from di.types.solved import SolvedDependant

Dependency = Any


class ExecutionPlan(NamedTuple):
    """Cache of the execution plan, stored within SolvedDependantCache"""

    # the cache_key is used to compare execution plans and know if we need to re-create it
    # for a given SolvedDependant if the cache_key is equal, the plans will be equal
    cache_key: FrozenSet[DependantBase[Any]]
    # mapping of which dependencies require computation for each dependant
    # it is possible that some of them were passed by value or cached
    # and hence do not require computation
    dependant_dag: Mapping[DependantBase[Any], Iterable[Task[Any]]]
    # count of how many uncompomputed dependencies each dependant has
    # this is used to keep track of what dependencies are now available for computation
    dependency_counts: Dict[DependantBase[Any], int]
    leaf_tasks: Iterable[Task[Any]]  # these are the tasks w/ no dependencies


class SolvedDependantCache(NamedTuple):
    """Private data that the Container attaches to SolvedDependant"""

    tasks: Mapping[DependantBase[Any], Task[Any]]
    dependency_dag: Mapping[DependantBase[Any], Set[DependantBase[Any]]]
    execution_plan: Optional[ExecutionPlan] = None


def plan_execution(
    state: ContainerState,
    solved: SolvedDependant[Any],
    *,
    validate_scopes: bool = True,
    values: Optional[Mapping[DependencyProvider, Any]] = None,
) -> Tuple[
    Dict[DependantBase[Any], Any],
    List[TaskInfo],
    Iterable[DependantBase[Any]],
]:
    """Re-use or create an ExecutionPlan"""
    user_values = values or {}
    if validate_scopes:
        scope_validation.validate_scopes(state.scopes, solved)

    if type(solved.container_cache) is not SolvedDependantCache:
        raise TypeError(
            "This SolvedDependant was not created by this Container"
        )  # pragma: no cover

    solved_dependency_cache: SolvedDependantCache = solved.container_cache

    # dump all cached values into one mapping for faster lookups
    # this relies on the fact that:
    # (1) dict.update is fast
    # (2) we will be doing a lot of lookups (one for each key in the DAG)
    # (3) this converts an iteration over scopes into a dict lookup
    cache: Dict[DependencyProvider, Any] = {}
    for mapping in state.cached_values.mappings.values():
        cache.update(mapping)
    cache.update(user_values)

    to_cache: Deque[DependantBase[Any]] = deque()
    execution_scope = state.scopes[-1]

    results: Dict[DependantBase[Any], Any] = {}

    # For each dependency, check if we can use a cached value or a user supplied value
    # If so, put that value into our results dict
    def use_cache(dep: DependantBase[Any]) -> None:
        call = dep.call
        if call in cache:
            if call in user_values:
                results[dep] = user_values[call]
                return
            elif dep.share:
                results[dep] = cache[call]
                return
        else:
            # skip caching the innermost scope since it would be dropped
            # right after saving the value
            if dep.share and dep.scope != execution_scope:
                # mark this dependency to have it's value stored in the cache
                # after we are done w/ this execution
                to_cache.append(dep)
        return

    for dep in solved.dag:
        use_cache(dep)

    execution_plan_cache_key = frozenset(results.keys())

    execution_plan = solved_dependency_cache.execution_plan

    # Check if we can re-use the existing plan (if any) or create a new one
    if execution_plan is None or execution_plan.cache_key != execution_plan_cache_key:
        # Build a DAG of Tasks that we actually need to execute
        # this allows us to prune subtrees that will come
        # from pre-computed values (values paramter or cache)
        unvisited = deque([solved.dependency])
        dependency_counts: Dict[DependantBase[Any], int] = {}
        dependant_dag: Dict[DependantBase[Any], Deque[Task[Any]]] = {
            dep: deque() for dep in solved_dependency_cache.dependency_dag
        }
        while unvisited:
            dep = unvisited.pop()
            if dep in dependency_counts:
                continue
            # if the dependency is cached or was provided by value
            # we don't need to compute it or any of it's dependencies
            if dep not in results:
                # otherwise, we add it to our DAG and visit it's children
                dependency_counts[dep] = 0
                for subdep in solved_dependency_cache.dependency_dag[dep]:
                    if subdep not in results:
                        dependant_dag[subdep].append(solved_dependency_cache.tasks[dep])
                        dependency_counts[dep] += 1
                        if subdep not in dependency_counts:
                            unvisited.append(subdep)

        execution_plan = ExecutionPlan(
            cache_key=execution_plan_cache_key,
            dependant_dag=dependant_dag,
            dependency_counts=dependency_counts,
            leaf_tasks=[
                solved_dependency_cache.tasks[dep]
                for dep, count in dependency_counts.items()
                if count == 0
            ],
        )

        solved.container_cache = SolvedDependantCache(
            tasks=solved_dependency_cache.tasks,
            dependency_dag=solved_dependency_cache.dependency_dag,
            execution_plan=execution_plan,
        )

    execution_state = ExecutionState(
        container_state=state,
        results=results,
        dependency_counts=execution_plan.dependency_counts.copy(),
        dependants=execution_plan.dependant_dag,
    )

    return (
        results,
        [t.as_executor_task(execution_state) for t in execution_plan.leaf_tasks],
        to_cache,
    )
