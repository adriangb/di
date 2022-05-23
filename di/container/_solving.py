import itertools
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Set, Tuple, TypeVar

from graphlib2 import CycleError, TopologicalSorter

from di._utils.task import Task
from di.api.dependencies import CacheKey, DependantBase, DependencyParameter
from di.api.scopes import Scope
from di.api.solved import SolvedDependant
from di.container._bind_hook import BindHook
from di.container._execution_planning import SolvedDependantCache
from di.container._scope_validation import validate_scopes
from di.container._utils import get_path, get_path_str
from di.exceptions import DependencyCycleError, SolvingError, WiringError

T = TypeVar("T")


def get_params(
    dep: "DependantBase[Any]",
    binds: Iterable[BindHook],
    parents: Mapping[DependantBase[Any], DependantBase[Any]],
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
                        f"\nPath: {get_path_str(dep, parents)}"
                    ),
                    path=get_path(dep, parents),
                )
    return params


def build_dag(
    dependency: DependantBase[Any],
    binds: Iterable[BindHook],
) -> Tuple[
    Mapping[DependantBase[Any], Iterable[DependencyParameter]],
    Mapping[DependantBase[Any], DependantBase[Any]],
]:
    """Build a forward DAG (parent -> children) and reversed dag (child -> parent).
    Checks for DAG cycles.
    """
    dag: "Dict[DependantBase[Any], List[DependencyParameter]]" = {}
    dependants: "Dict[CacheKey, DependantBase[Any]]" = {}
    # Keep track of the parents of each dependency so that we can reconstruct a path to it
    parents: "Dict[DependantBase[Any], DependantBase[Any]]" = {}

    q: "List[DependantBase[Any]]" = [dependency]
    seen: "Set[DependantBase[Any]]" = set()
    while q:
        dep = q.pop()
        seen.add(dep)
        cache_key = dep.cache_key
        if cache_key in dependants:
            other = dependants[cache_key]
            if other.scope != dep.scope:
                raise SolvingError(
                    (
                        f"The dependency {dep.call} is used with multiple scopes"
                        f" ({dep.scope} and {other.scope}); this is not allowed."
                        f"\nPath: {get_path_str(dep, parents)}"
                    ),
                    get_path(dep, parents),
                )
            continue  # pragma: no cover
        dependants[cache_key] = dep
        params = get_params(dep, binds, parents)
        dag[dep] = params
        for param in params:
            predecessor_dep = param.dependency
            parents[predecessor_dep] = dep
            if predecessor_dep not in seen:
                q.append(predecessor_dep)
    # filter out dependencies that are not callable
    dag = {
        d: [s for s in dag[d] if s.dependency.call is not None]
        for d in dag
        if d.call is not None
    }
    # check for cycles in callables, dependant instances are unique
    try:
        TopologicalSorter(
            {
                dep.call: [p.dependency.call for p in params]
                for dep, params in dag.items()
            }
        ).prepare()
    except CycleError as e:
        dep = next(iter(reversed(e.args[1])))
        raise DependencyCycleError(
            f"Nodes are in a cycle.\nPath: {get_path_str(dep, parents)}",
            path=get_path(dep, parents),
        ) from e
    # make sure all values have a key
    # e.g. {1: [2]} -> {1: [2], 2: []}
    dag = {
        d: dag.get(d, [])
        for d in itertools.chain(
            *((v.dependency for v in vs) for vs in dag.values()), dag.keys()
        )
    }
    return dag, parents


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

    dag, parents = build_dag(dependency, binds)

    # Order the Dependant's topologically so that we can create Tasks
    # with references to all of their children
    dep_topsort = tuple(
        TopologicalSorter(
            {dep: [p.dependency for p in params] for dep, params in dag.items()}
        ).static_order()
    )
    # Create a separate TopologicalSorter to hold the Tasks
    ts: "TopologicalSorter[Task]" = TopologicalSorter()
    tasks = build_tasks(dag, dep_topsort, ts)
    static_order = tuple(ts.copy().static_order())
    ts.prepare()
    assert dependency.call is not None
    container_cache = SolvedDependantCache(
        root_task=tasks[dependency],
        topological_sorter=ts,
        static_order=static_order,
        empty_results=[None] * len(tasks),
    )
    validate_scopes(scopes, {d: [s.dependency for s in dag[d]] for d in dag}, parents)
    solved = SolvedDependant(
        dependency=dependency,
        dag=dag,
        container_cache=container_cache,
    )
    return solved


def build_tasks(
    dag: Mapping[
        DependantBase[Any],
        Iterable[DependencyParameter],
    ],
    topsorted: Iterable[DependantBase[Any]],
    ts: TopologicalSorter[Task],
) -> Dict[DependantBase[Any], Task]:
    tasks: Dict[DependantBase[Any], Task] = {}
    task_id = 0
    for dep in topsorted:
        positional: List[Task] = []
        keyword: Dict[str, Task] = {}
        for param in dag[dep]:
            if param.parameter is not None:
                assert param.dependency.call is not None
                task = tasks[param.dependency]
                if param.parameter.kind is param.parameter.KEYWORD_ONLY:
                    keyword[param.parameter.name] = task
                else:
                    positional.append(task)

        positional_parameters = tuple(positional)
        keyword_parameters = tuple((k, v) for k, v in keyword.items())

        assert dep.call is not None
        tasks[dep] = task = Task(
            scope=dep.scope,
            call=dep.call,
            use_cache=dep.use_cache,
            cache_key=dep.cache_key,
            dependant=dep,
            task_id=task_id,
            positional_parameters=positional_parameters,
            keyword_parameters=keyword_parameters,
        )
        task_id += 1
        ts.add(
            task,
            *(tasks[p.dependency] for p in dag[dep] if p.dependency.call is not None),
        )
    return tasks
