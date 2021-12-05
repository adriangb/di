from __future__ import annotations

from collections import deque
from contextlib import AsyncExitStack, ExitStack
from typing import (
    AbstractSet,
    Any,
    Deque,
    Dict,
    Iterable,
    Mapping,
    NamedTuple,
    Optional,
    Set,
    Tuple,
    Union,
)

from graphlib2 import TopologicalSorter

from di._utils.scope_validation import validate_scopes
from di._utils.task import AsyncTask, ExecutionState, SyncTask, gather_new_tasks
from di.api.dependencies import DependantBase
from di.api.executor import State as ExecutorState
from di.api.executor import Task as ExecutorTask
from di.api.providers import DependencyProvider
from di.api.scopes import Scope
from di.api.solved import SolvedDependant

Dependency = Any

Task = Union[AsyncTask, SyncTask]

TaskCacheDeque = Deque[Tuple[Task, Scope]]

Results = Dict[Task, Any]

TaskDependencyCounts = Dict[Task, int]


class SolvedDependantCache(NamedTuple):
    """Private data that the Container attaches to SolvedDependant"""

    root_task: Task
    topological_sorter: TopologicalSorter[Task]
    cacheable_tasks: AbstractSet[Task]
    cached_tasks: Iterable[Tuple[Task, Scope]]
    validated_scopes: Set[Tuple[Scope, ...]]
    call_map: Mapping[DependencyProvider, Iterable[Task]]


def plan_execution(
    stacks: Mapping[Scope, Union[AsyncExitStack, ExitStack]],
    cached_values: Mapping[DependantBase[Any], Any],
    solved: SolvedDependant[Any],
    *,
    values: Optional[Mapping[DependencyProvider, Any]] = None,
) -> Tuple[
    Dict[Task, Any],
    Iterable[Optional[ExecutorTask]],
    ExecutorState,
    Iterable[Tuple[Task, Scope]],
    Task,
]:
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
    call_map = solved_dependency_cache.call_map
    for call in user_values.keys() & call_map.keys():
        value = user_values[call]
        for task_id in call_map[call]:
            results[task_id] = value

    to_cache: TaskCacheDeque = deque()
    cacheable_tasks = solved_dependency_cache.cacheable_tasks
    add_to_cache = to_cache.append

    for task, scope in solved_dependency_cache.cached_tasks:
        if task.dependant in cached_values:
            results[task] = cached_values[task.dependant]
        elif task in cacheable_tasks:
            add_to_cache((task, scope))

    ts = solved_dependency_cache.topological_sorter.copy()

    execution_state = ExecutionState(
        stacks=stacks,
        results=results,
        toplogical_sorter=ts,
    )

    return (
        results,
        gather_new_tasks(execution_state),
        ExecutorState(execution_state),
        to_cache,
        solved_dependency_cache.root_task,
    )
