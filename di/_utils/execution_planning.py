from __future__ import annotations

from collections import deque
from contextlib import AsyncExitStack, ExitStack
from typing import (
    AbstractSet,
    Any,
    Deque,
    Dict,
    Iterable,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Set,
    Tuple,
    Union,
)

from di._utils.scope_validation import validate_scopes
from di._utils.task import ExecutionState, Task
from di.api.dependencies import DependantBase
from di.api.executor import TaskInfo
from di.api.providers import DependencyProvider
from di.api.scopes import Scope
from di.api.solved import SolvedDependant

Dependency = Any

TaskDeque = Deque[Task]

Results = Dict[Task, Any]

TaskDependencyCounts = Dict[Task, int]


class ExecutionPlan(NamedTuple):
    """Cache of the execution plan, stored within SolvedDependantCache"""

    cache_key: AbstractSet[Task]
    # mapping of which dependencies require computation for each dependant
    # it is possible that some of them were passed by value or cached
    # and hence do not require computation
    task_dependant_dag: Mapping[Task, Iterable[Task]]
    # count of how many uncompomputed dependencies each dependant has
    # this is used to keep track of what dependencies are now available for computation
    dependency_counts: Dict[Task, int]
    leaf_tasks: Iterable[Task]  # these are the tasks w/ no dependencies


class SolvedDependantCache(NamedTuple):
    """Private data that the Container attaches to SolvedDependant"""

    root_task: Task
    task_dependency_dag: Mapping[Task, Set[Task]]
    task_dependant_dag: Mapping[Task, Set[Task]]
    execution_plan: Optional[ExecutionPlan]
    cacheable_tasks: AbstractSet[Task]
    cached_tasks: AbstractSet[Task]
    validated_scopes: Set[Tuple[Scope, ...]]
    call_map: Mapping[DependencyProvider, Set[Task]]


def make_execution_plan(
    resolved_tasks: AbstractSet[Task],
    root_task: Task,
    task_dependency_dag: Mapping[Task, Set[Task]],
    task_dependant_dag: Mapping[Task, Set[Task]],
) -> ExecutionPlan:
    # Build a DAG of Tasks that we actually need to execute
    # this allows us to prune subtrees that will come
    # from pre-computed values (values paramter or cache)
    unvisited = deque((root_task,))
    dependency_counts: TaskDependencyCounts = {}
    while unvisited:
        task = unvisited.pop()
        # if the dependency is cached or was provided by value
        # we don't need to compute it or any of it's dependencies
        if task in resolved_tasks:
            continue
        # we can also skip this dep if it's already been accounted for
        if task in dependency_counts:
            continue
        # otherwise, we add it to our DAG and visit it's children
        dependency_counts[task] = 0
        for predecessor_task in task_dependency_dag[task]:
            if predecessor_task not in resolved_tasks:
                dependency_counts[task] += 1
                if predecessor_task not in dependency_counts:
                    unvisited.append(predecessor_task)

    return ExecutionPlan(
        cache_key=frozenset(resolved_tasks),
        task_dependant_dag=task_dependant_dag,
        dependency_counts=dependency_counts,
        leaf_tasks=[task for task, count in dependency_counts.items() if count == 0],
    )


def plan_execution(
    stacks: Mapping[Scope, Union[AsyncExitStack, ExitStack]],
    cached_values: Mapping[DependantBase[Any], Any],
    solved: SolvedDependant[Any],
    *,
    values: Optional[Mapping[DependencyProvider, Any]] = None,
) -> Tuple[Dict[Task, Any], List[TaskInfo], Iterable[Task], Task]:
    """Re-use or create an ExecutionPlan"""
    # This function is a hot loop
    # It is run for every execution, and even with the cache it can be a bottleneck
    # This would be the best place to Cythonize or otherwise take more drastic measures

    user_values = values or {}

    solved_dependency_cache: SolvedDependantCache = solved.container_cache

    scopes = tuple(stacks.keys())
    if scopes not in solved_dependency_cache.validated_scopes:
        validate_scopes(scopes, solved.dag)
        solved_dependency_cache.validated_scopes.add(scopes)

    results: Results = {}
    for call, value in user_values.items():
        for task in solved_dependency_cache.call_map[call]:
            results[task] = value

    to_cache: TaskDeque = deque()

    for task in solved_dependency_cache.cached_tasks:
        if task.dependant in cached_values:
            results[task] = cached_values[task.dependant]
        elif task in solved_dependency_cache.cacheable_tasks:
            to_cache.append(task)

    execution_plan = solved_dependency_cache.execution_plan
    resolved_tasks = results.keys()

    # Check if we can re-use the existing plan (if any) or create a new one
    if execution_plan is None or execution_plan.cache_key != resolved_tasks:
        execution_plan = make_execution_plan(
            resolved_tasks,
            solved_dependency_cache.root_task,
            solved_dependency_cache.task_dependency_dag,
            solved_dependency_cache.task_dependant_dag,
        )
        solved.container_cache = solved_dependency_cache._replace(
            execution_plan=execution_plan
        )

    execution_state = ExecutionState(
        stacks=stacks,
        results=results,
        dependency_counts=execution_plan.dependency_counts.copy(),
        dependants=execution_plan.task_dependant_dag,
    )

    return (
        results,
        [t.as_executor_task(execution_state) for t in execution_plan.leaf_tasks],
        to_cache,
        solved_dependency_cache.root_task,
    )
