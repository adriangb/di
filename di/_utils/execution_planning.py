from __future__ import annotations

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

from di._utils.scope_map import ScopeMap
from di._utils.scope_validation import validate_scopes
from di._utils.task import AsyncTask, ExecutionState, SyncTask, gather_new_tasks
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
    tasks_that_we_can_cache: AbstractSet[Task]
    tasks_that_can_be_pulled_from_cache: Iterable[Tuple[Task, Scope]]
    validated_scopes: Set[Tuple[Scope, ...]]
    callable_to_task_mapping: Mapping[DependencyProvider, Iterable[Task]]


def plan_execution(
    stacks: Mapping[Scope, Union[AsyncExitStack, ExitStack]],
    cache: ScopeMap[DependencyProvider, Any],
    solved: SolvedDependant[Any],
    *,
    values: Optional[Mapping[DependencyProvider, Any]] = None,
) -> Tuple[Dict[Task, Any], Iterable[Optional[ExecutorTask]], ExecutorState, Task,]:
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
    call_map = solved_dependency_cache.callable_to_task_mapping
    for call in user_values.keys() & call_map.keys():
        value = user_values[call]
        for task_id in call_map[call]:
            results[task_id] = value

    ts = solved_dependency_cache.topological_sorter.copy()

    execution_state = ExecutionState(
        stacks=stacks,
        results=results,
        toplogical_sorter=ts,
        cache=cache,
    )

    return (
        results,
        gather_new_tasks(execution_state),
        ExecutorState(execution_state),
        solved_dependency_cache.root_task,
    )
