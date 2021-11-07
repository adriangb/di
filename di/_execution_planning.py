import functools
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
from di.types.dependencies import DependantProtocol
from di.types.executor import Task as ExecutorTask
from di.types.providers import DependencyProvider
from di.types.solved import SolvedDependency

Dependency = Any


class ExecutionPlanCache(NamedTuple):
    cache_key: FrozenSet[DependantProtocol[Any]]
    dependant_dag: Mapping[DependantProtocol[Any], Iterable[Task[Any]]]
    dependency_counts: Dict[DependantProtocol[Any], int]
    leaf_tasks: Iterable[Task[Any]]


class SolvedDependencyCache(NamedTuple):
    tasks: Mapping[DependantProtocol[Any], Task[Any]]
    dependency_dag: Mapping[DependantProtocol[Any], Set[DependantProtocol[Any]]]
    execution_plan: Optional[ExecutionPlanCache] = None


def plan_execution(
    state: ContainerState,
    solved: SolvedDependency[Any],
    *,
    validate_scopes: bool = True,
    values: Optional[Mapping[DependencyProvider, Any]] = None,
) -> Tuple[
    Dict[DependantProtocol[Any], Any],
    List[ExecutorTask],
    Iterable[DependantProtocol[Any]],
]:
    user_values = values or {}
    if validate_scopes:
        scope_validation.validate_scopes(state.scopes, solved)

    if type(solved.container_cache) is not SolvedDependencyCache:
        raise TypeError(
            "This SolvedDependency was not created by this Container"
        )  # pragma: no cover

    solved_dependency_cache: SolvedDependencyCache = solved.container_cache

    cache: Dict[DependencyProvider, Any] = {}
    for mapping in state.cached_values.mappings.values():
        cache.update(mapping)
    cache.update(user_values)

    to_cache: Deque[DependantProtocol[Any]] = deque()
    execution_scope = state.scopes[-1]

    results: Dict[DependantProtocol[Any], Any] = {}

    def use_cache(dep: DependantProtocol[Any]) -> None:
        call = dep.call
        if call in cache:
            if call in user_values:
                results[dep] = user_values[call]
                return
            elif dep.share:
                results[dep] = cache[call]
                return
        else:
            if dep.share and dep.scope != execution_scope:
                to_cache.append(dep)
        return

    for dep in solved.dag:
        use_cache(dep)

    execution_plan_cache_key = frozenset(results.keys())

    execution_plan = solved_dependency_cache.execution_plan

    if execution_plan is None or execution_plan.cache_key != execution_plan_cache_key:
        # Build a DAG of Tasks that we actually need to execute
        # this allows us to prune subtrees that will come
        # from pre-computed values (values paramter or cache)
        unvisited = deque([solved.dependency])
        # Make DAG values a set to account for dependencies that depend on the the same
        # sub dependency in more than one param (`def func(a: A, a_again: A)`)
        dependency_counts: Dict[DependantProtocol[Any], int] = {}
        dependant_dag: Dict[DependantProtocol[Any], Deque[Task[Any]]] = {
            dep: deque() for dep in solved_dependency_cache.dependency_dag
        }
        while unvisited:
            dep = unvisited.pop()
            if dep in dependency_counts:
                continue
            # task the dependency is cached or was provided by value
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

        execution_plan = ExecutionPlanCache(
            cache_key=execution_plan_cache_key,
            dependant_dag=dependant_dag,
            dependency_counts=dependency_counts,
            leaf_tasks=[
                solved_dependency_cache.tasks[dep]
                for dep, count in dependency_counts.items()
                if count == 0
            ],
        )

        solved.container_cache = SolvedDependencyCache(
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
        [
            functools.partial(t.compute, execution_state)  # type: ignore[arg-type]
            for t in execution_plan.leaf_tasks
        ],
        to_cache,
    )
