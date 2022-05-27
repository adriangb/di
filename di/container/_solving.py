from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Sequence,
    Set,
    Tuple,
    TypeVar,
)

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


def resolve_unset_scopes(
    dep_scopes: Sequence[Scope], scopes: Sequence[Scope]
) -> Sequence[Scope]:
    if None in scopes or not scopes:
        # None is a valid scope, so we have no unset scopes
        return dep_scopes
    scope_idxs = dict((scope, idx) for idx, scope in enumerate(scopes))
    current = scopes[0]
    # If we have A("app"), B("request"), C(None) and C depends on B which depends on A
    # we need to set C's scope to "request".
    # For this case dep_scopes = [None, "request", "app"]
    # If we have A("app"), B(None) B gets "app" scope
    # Here dep_scopes = [None, "app"]
    res: "List[Scope]" = []
    for scope in dep_scopes:
        if scope is None:
            scope = current
        elif scope_idxs[scope] > scope_idxs[current]:
            current = scope
        res.append(scope)
    return res


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
        level = q.copy()
        q.clear()
        for dep in level:
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
    dag = {
        dependants[d.cache_key]: [
            s._replace(dependency=dependants[s.dependency.cache_key]) for s in dag[d]
        ]
        for d in dag
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

    def get_scope(dep: "DependantBase[Any]") -> Scope:
        if dep.scope is not None:
            return dep.scope
        if None in scopes:
            return dep.scope
        path = get_path(dep, parents)
        dep_scopes = [d.scope for d in path]
        # dep is the last dependency in path
        return next(iter(reversed(resolve_unset_scopes(dep_scopes, scopes))))

    # Order the Dependant's topologically so that we can create Tasks
    # with references to all of their children
    dep_topsort = tuple(
        TopologicalSorter(
            {dep: [p.dependency for p in params] for dep, params in dag.items()}
        ).static_order()
    )
    # Create a separate TopologicalSorter to hold the Tasks
    ts: "TopologicalSorter[Task]" = TopologicalSorter()
    tasks = build_tasks(dag, dep_topsort, ts, get_scope)
    static_order = tuple(ts.copy().static_order())
    ts.prepare()
    assert dependency.call is not None
    container_cache = SolvedDependantCache(
        root_task=tasks[dependency],
        topological_sorter=ts,
        static_order=static_order,
        empty_results=[None] * len(tasks),
    )
    # at this point the call is never None
    # but type checkers don't know this, hence the filtering
    call_dag = {
        dep.call: [
            subdep.dependency.call
            for subdep in dag[dep]
            if subdep.dependency.call is not None
        ]
        for dep in dag
        if dep.call is not None
    }
    call_parents = {
        dep.call: parent.call
        for dep, parent in parents.items()
        if dep.call is not None and parent.call is not None
    }
    dep_scopes = {dep.call: tasks[dep].scope for dep in dag if dep.call is not None}
    validate_scopes(scopes, dag=call_dag, parents=call_parents, dep_scopes=dep_scopes)
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
    get_scope: Callable[[DependantBase[Any]], Scope],
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
            scope=get_scope(dep),
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
