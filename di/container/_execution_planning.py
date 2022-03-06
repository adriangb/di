from contextlib import AsyncExitStack, ExitStack
from typing import Any, Dict, Iterable, Mapping, NamedTuple, Optional, Tuple, Union

from graphlib2 import TopologicalSorter

from di._utils.scope_map import ScopeMap
from di._utils.task import ExecutionState, Task
from di._utils.types import CacheKey
from di.api.executor import Task as ExecutorTask
from di.api.executor import TaskGraph as SupportsTaskGraph
from di.api.providers import DependencyProvider
from di.api.scopes import Scope
from di.api.solved import SolvedDependant

Results = Dict[int, Any]


class TaskGraph:
    __slots__ = ("_uncopied_ts", "_copied_ts", "_static_order")
    _copied_ts: Optional[TopologicalSorter[ExecutorTask]]

    def __init__(
        self,
        ts: TopologicalSorter[ExecutorTask],
        static_order: Iterable[ExecutorTask],
    ) -> None:
        self._uncopied_ts = ts
        self._copied_ts = None
        self._static_order = static_order

    def get_ready(self) -> Iterable[ExecutorTask]:
        if self._copied_ts is None:
            self._copied_ts = self._uncopied_ts.copy()
        return self._copied_ts.get_ready()

    def done(self, task: ExecutorTask) -> None:
        if self._copied_ts is None:
            self._copied_ts = self._uncopied_ts.copy()
        self._copied_ts.done(task)

    def is_active(self) -> bool:
        if self._copied_ts is None:
            self._copied_ts = self._uncopied_ts.copy()
        return self._copied_ts.is_active()

    def static_order(self) -> Iterable[ExecutorTask]:
        return self._static_order


class SolvedDependantCache(NamedTuple):
    """Private data that the Container attaches to SolvedDependant"""

    root_task: Task
    topological_sorter: TopologicalSorter[Task]
    static_order: Iterable[Task]


def plan_execution(
    stacks: Mapping[Scope, Union[AsyncExitStack, ExitStack]],
    cache: ScopeMap[CacheKey, Any],
    solved: SolvedDependant[Any],
    *,
    values: Optional[Mapping[DependencyProvider, Any]] = None,
) -> Tuple[Dict[int, Any], SupportsTaskGraph, Any, Task,]:
    solved_dependency_cache: "SolvedDependantCache" = solved.container_cache
    results: "Results" = {}
    execution_state = ExecutionState(
        values=values or {},
        stacks=stacks,
        results=results,
        cache=cache,
    )
    # the type of TopologicalSorter[ExecutorTask] is not strictly
    # compatible with TopologicalSorter[Task]
    ts = TaskGraph(
        solved_dependency_cache.topological_sorter,  # type: ignore[arg-type]
        solved_dependency_cache.static_order,
    )
    return (
        results,
        ts,
        execution_state,
        solved_dependency_cache.root_task,
    )
