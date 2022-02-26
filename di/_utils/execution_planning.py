from __future__ import annotations

from contextlib import AsyncExitStack, ExitStack
from typing import Any, Dict, Iterable, Mapping, NamedTuple, Optional, Tuple, Union

from graphlib2 import TopologicalSorter

from di._utils.scope_map import ScopeMap
from di._utils.task import ExecutionState, Task, gather_new_tasks
from di._utils.types import CacheKey
from di.api.executor import Task as ExecutorTask
from di.api.providers import DependencyProvider
from di.api.scopes import Scope
from di.api.solved import SolvedDependant

Results = Dict[int, Any]


class SolvedDependantCache(NamedTuple):
    """Private data that the Container attaches to SolvedDependant"""

    root_task: Task
    topological_sorter: TopologicalSorter[Task]


def plan_execution(
    stacks: Mapping[Scope, Union[AsyncExitStack, ExitStack]],
    cache: ScopeMap[CacheKey, Any],
    solved: SolvedDependant[Any],
    *,
    values: Optional[Mapping[DependencyProvider, Any]] = None,
) -> Tuple[Dict[int, Any], Iterable[Optional[ExecutorTask]], Any, Task,]:
    solved_dependency_cache: "SolvedDependantCache" = solved.container_cache
    ts = solved_dependency_cache.topological_sorter.copy()
    results: "Results" = {}
    execution_state = ExecutionState(
        values=values or {},
        stacks=stacks,
        results=results,
        toplogical_sorter=ts,
        cache=cache,
    )
    return (
        results,
        gather_new_tasks(execution_state),
        execution_state,
        solved_dependency_cache.root_task,
    )
