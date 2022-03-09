from contextlib import AsyncExitStack, ExitStack
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Tuple,
    Union,
    cast,
)

from graphlib2 import TopologicalSorter

from di._utils.scope_map import ScopeMap
from di._utils.task import ExecutionState, Task
from di._utils.types import CacheKey
from di.api.executor import SupportsTaskGraph
from di.api.executor import Task as SupportsTask
from di.api.providers import DependencyProvider
from di.api.scopes import Scope
from di.api.solved import SolvedDependant


class TaskGraph:
    __slots__ = ("_uncopied_ts", "_copied_ts", "_static_order")
    _copied_ts: Optional[TopologicalSorter[Task]]

    def __init__(
        self,
        ts: TopologicalSorter[Task],
        static_order: Iterable[Task],
    ) -> None:
        self._uncopied_ts = ts
        self._copied_ts = None
        self._static_order = static_order

    def get_ready(self) -> Iterable[Task]:
        if self._copied_ts is None:
            self._copied_ts = self._uncopied_ts.copy()
        return self._copied_ts.get_ready()

    def done(self, task: SupportsTask[ExecutionState]) -> None:
        if self._copied_ts is None:
            self._copied_ts = self._uncopied_ts.copy()
        self._copied_ts.done(cast(Task, task))

    def is_active(self) -> bool:
        if self._copied_ts is None:
            self._copied_ts = self._uncopied_ts.copy()
        return self._copied_ts.is_active()

    def static_order(self) -> Iterable[Task]:
        return self._static_order


class SolvedDependantCache(NamedTuple):
    """Private data that the Container attaches to SolvedDependant"""

    root_task: Task
    topological_sorter: TopologicalSorter[Task]
    static_order: Iterable[Task]
    empty_results: List[Any]


EMPTY_VALUES: Dict[DependencyProvider, Any] = {}


def plan_execution(
    stacks: Mapping[Scope, Union[AsyncExitStack, ExitStack]],
    cache: ScopeMap[CacheKey, Any],
    solved: SolvedDependant[Any],
    values: Optional[Mapping[DependencyProvider, Any]] = None,
) -> Tuple[List[Any], SupportsTaskGraph[ExecutionState], ExecutionState, Task,]:
    solved_dependency_cache: SolvedDependantCache = solved.container_cache
    results = solved_dependency_cache.empty_results.copy()
    if values is None:
        values = EMPTY_VALUES
    execution_state = ExecutionState(
        values=values,
        stacks=stacks,
        results=results,
        cache=cache,
    )
    ts = TaskGraph(
        solved_dependency_cache.topological_sorter,
        solved_dependency_cache.static_order,
    )
    return (
        results,
        ts,
        execution_state,
        solved_dependency_cache.root_task,
    )
