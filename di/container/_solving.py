import inspect
from typing import Any, Dict, Iterable, List, Mapping, Sequence, TypeVar

from graphlib2 import TopologicalSorter

from di._utils.task import Task
from di.api.dependencies import CacheKey, DependantBase, DependencyParameter
from di.api.scopes import Scope
from di.api.solved import SolvedDependant
from di.container._bind_hook import BindHook
from di.container._execution_planning import SolvedDependantCache
from di.exceptions import (
    DependencyCycleError,
    ScopeViolationError,
    SolvingError,
    UnknownScopeError,
    WiringError,
)

T = TypeVar("T")


POSITIONAL_PARAMS = (
    inspect.Parameter.POSITIONAL_ONLY,
    inspect.Parameter.POSITIONAL_OR_KEYWORD,
)


def get_path_str(path: Iterable[DependantBase[Any]]) -> str:
    return " -> ".join(
        [repr(item) if item.call is not None else repr(item.call) for item in path]
    )


def get_params(
    dep: DependantBase[Any],
    binds: Iterable[BindHook],
    path: Iterable[DependantBase[Any]],
) -> "List[DependencyParameter]":
    """Get Dependants for parameters and resolve binds"""
    params = dep.get_dependencies().copy()
    for idx, param in enumerate(params):
        for hook in binds:
            match = hook(param.parameter, param.dependency)
            if match is not None:
                param = param._replace(dependency=match)
        params[idx] = param
        if param.parameter is not None:
            if (
                param.dependency.call is None
                and param.parameter.default is param.parameter.empty
            ):
                raise WiringError(
                    (
                        f"The parameter {param.parameter.name} to {dep.call} has no dependency marker,"
                        " no type annotation and no default value."
                        " This will produce a TypeError when this function is called."
                        " You must either provide a dependency marker, a type annotation or a default value."
                        f"\nPath: {get_path_str([*path, dep])}"
                    ),
                    path=[*path, dep],
                )
    return params


def check_task_scope_validity(
    task: Task,
    subtasks: Iterable[Task],
    scopes: Mapping[Scope, int],
    path: Iterable[DependantBase[Any]],
) -> None:
    if task.scope not in scopes:
        raise UnknownScopeError(
            f"Dependency{task.dependant} has an unknown scope {task.scope}."
            f"\nExample Path: {get_path_str(path)}"
        )
    for subtask in subtasks:
        if scopes[task.scope] < scopes[subtask.scope]:
            raise ScopeViolationError(
                f"{task.dependant.call} cannot depend on {subtask.dependant.call}"
                f" because {subtask.dependant.call}'s scope ({subtask.scope})"
                f" is narrower than {task.dependant.call}'s scope ({task.scope})"
                f"\nExample Path: {get_path_str(path)}"
            )


def build_task(
    dependency: DependantBase[Any],
    binds: Iterable[BindHook],
    tasks: Dict[CacheKey, Task],
    task_dag: Dict[Task, List[Task]],
    dependant_dag: Dict[DependantBase[Any], List[DependencyParameter]],
    path: Dict[DependantBase[Any], Any],
    scope_idxs: Mapping[Scope, int],
) -> Task:

    call = dependency.call
    assert call is not None
    scope = dependency.scope

    if dependency.call in {d.call for d in path}:
        raise DependencyCycleError(
            "Dependencies are in a cycle",
            list(path.keys()),
        )

    if dependency.cache_key in tasks:
        if tasks[dependency.cache_key].scope != dependency.scope:
            raise SolvingError(
                f"{dependency.call} was used with multiple scopes",
                path=list(path.keys()),
            )
        return tasks[dependency.cache_key]

    params = get_params(dependency, binds, path)

    positional_parameters: "List[Task]" = []
    keyword_parameters: "Dict[str, Task]" = {}
    subtasks: "List[Task]" = []
    dependant_dag[dependency] = []

    path[dependency] = None  # any value will do, we only use the keys

    for param in params:
        dependant_dag[dependency].append(param)
        if param.dependency.call is not None:
            child_task = build_task(
                param.dependency,
                binds,
                tasks,
                task_dag,
                dependant_dag,
                path,
                scope_idxs,
            )
            subtasks.append(child_task)
            if param.parameter is not None:
                if param.parameter.kind in POSITIONAL_PARAMS:
                    positional_parameters.append(child_task)
                else:
                    keyword_parameters[param.parameter.name] = child_task
        if (
            param.dependency not in dependant_dag
            and param.dependency.cache_key not in tasks
        ):
            dependant_dag[param.dependency] = []

    task = Task(
        dependant=dependency,
        scope=scope,
        call=call,
        cache_key=dependency.cache_key,
        task_id=len(tasks),
        positional_parameters=positional_parameters,
        keyword_parameters=keyword_parameters,
        use_cache=dependency.use_cache,
    )
    tasks[dependency.cache_key] = task
    task_dag[task] = subtasks
    check_task_scope_validity(
        task,
        subtasks,
        scope_idxs,
        path,
    )
    # remove ourselves from the path
    path.pop(dependency)
    return task


def solve(
    dependency: DependantBase[T],
    scopes: Sequence[Scope],
    binds: Iterable[BindHook],
) -> SolvedDependant[T]:
    """Solve a dependency.

    Returns a SolvedDependant that can be executed to get the dependency's value.
    """
    # If the dependency itself is a bind, replace it
    for hook in binds:
        match = hook(None, dependency)
        if match:
            dependency = match

    if dependency.call is None:  # pragma: no cover
        raise ValueError("DependantBase.call must not be None")

    task_dag: "Dict[Task, List[Task]]" = {}
    dep_dag: "Dict[DependantBase[Any], List[DependencyParameter]]" = {}
    scope_idxs = dict((scope, idx) for idx, scope in enumerate(scopes))

    # this is implemented recursively
    # which will crash on DAGs with depth > 1000 (default recursion limit)
    # if we encounter that in a real world use case
    # we can just rewrite this to be iterative
    root_task = build_task(
        dependency=dependency,
        binds=binds,
        tasks={},
        task_dag=task_dag,
        dependant_dag=dep_dag,
        # we use a dict to represent the path so that we can have
        # both O(1) lookups, and an ordered mutable sequence (via dict keys)
        # we simply ignore / don't use the dict values
        path={},
        scope_idxs=scope_idxs,
    )

    ts = TopologicalSorter(task_dag)
    static_order = tuple(ts.copy().static_order())
    ts.prepare()
    assert dependency.call is not None
    container_cache = SolvedDependantCache(
        root_task=root_task,
        topological_sorter=ts,
        static_order=static_order,
        empty_results=[None] * len(task_dag),
    )
    solved = SolvedDependant(
        dependency=dependency,
        dag=dep_dag,
        container_cache=container_cache,
    )
    return solved
