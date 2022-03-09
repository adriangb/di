from collections import deque
from typing import Any, Deque, Dict, Iterable, List, Sequence, Set, TypeVar

from graphlib2 import CycleError, TopologicalSorter

from di._utils.task import Task
from di.api.dependencies import CacheKey, DependantBase, DependencyParameter
from di.api.scopes import Scope
from di.api.solved import SolvedDependant
from di.container._bind_hook import BindHook
from di.container._execution_planning import SolvedDependantCache
from di.container._scope_validation import validate_scopes
from di.exceptions import DependencyCycleError, SolvingError, WiringError

T = TypeVar("T")


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

    dependants: Dict[CacheKey, DependantBase[Any]] = {}
    # DAG mapping dependants to their dependendencies
    dep_dag: Dict[DependantBase[Any], List[DependantBase[Any]]] = {}
    # The same DAG as above but including parameters (inspect.Parameter instances)
    param_graph: Dict[DependantBase[Any], List[DependencyParameter]] = {}

    def get_params(
        dep: DependantBase[Any],
    ) -> List[DependencyParameter]:
        # get parameters and swap them out w/ binds when they
        # exist as a bound value
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
                        f"The parameter {param.parameter.name} to {dep.call} has no dependency marker,"
                        " no type annotation and no default value."
                        " This will produce a TypeError when this function is called."
                        " You must either provide a dependency marker, a type annotation or a default value."
                    )
        return params

    # Do a DFS of the DAG checking constraints along the way
    q: Deque[DependantBase[Any]] = deque([dependency])
    seen: Set[DependantBase[Any]] = set()
    while q:
        dep = q.popleft()
        seen.add(dep)
        cache_key = dep.cache_key
        if cache_key in dependants:
            other = dependants[cache_key]
            if other.scope != dep.scope:
                raise SolvingError(
                    f"The dependency {dep.call} is used with multiple scopes"
                    f" ({dep.scope} and {other.scope}); this is not allowed."
                )
            continue  # pragma: no cover
        dependants[cache_key] = dep
        params = get_params(dep)
        param_graph[dep] = params
        dep_dag[dep] = []
        for param in params:
            predecessor_dep = param.dependency
            dep_dag[dep].append(predecessor_dep)
            if predecessor_dep not in seen:
                q.append(predecessor_dep)
    # Filter out any dependencies that do not have a call
    # These do not become tasks since they don't need to be computed
    computable_param_graph = {
        dep: [param for param in param_graph[dep] if param.dependency.call is not None]
        for dep in param_graph
        if dep.call is not None
    }
    # Order the Dependant's topologically so that we can create Tasks
    # with references to all of their children
    try:
        dep_topsort = tuple(
            TopologicalSorter(
                {
                    dep.cache_key: [p.dependency.cache_key for p in params]
                    for dep, params in computable_param_graph.items()
                }
            ).static_order()
        )
    except CycleError as e:
        raise DependencyCycleError("Nodes are in a cycle") from e
    # Create a seperate TopologicalSorter to hold the Tasks
    ts: TopologicalSorter[Task] = TopologicalSorter()
    tasks = build_tasks(
        computable_param_graph,
        (dependants[key] for key in dep_topsort),
        ts,
    )
    static_order = tuple(ts.copy().static_order())
    ts.prepare()
    container_cache = SolvedDependantCache(
        root_task=tasks[dependency.cache_key],
        topological_sorter=ts,
        static_order=static_order,
        empty_results=[None] * len(tasks),
    )
    validate_scopes(scopes, dep_dag)
    solved = SolvedDependant(
        dependency=dependency,
        dag=param_graph,
        container_cache=container_cache,
    )
    return solved


def build_tasks(
    dag: Dict[
        DependantBase[Any],
        List[DependencyParameter],
    ],
    topsorted: Iterable[DependantBase[Any]],
    ts: TopologicalSorter[Task],
) -> Dict[CacheKey, Task]:
    tasks: Dict[CacheKey, Task] = {}
    task_id = 0
    for dep in topsorted:
        positional: List[Task] = []
        keyword: Dict[str, Task] = {}
        for param in dag[dep]:
            if param.parameter is not None:
                task = tasks[param.dependency.cache_key]
                if param.parameter.kind is param.parameter.KEYWORD_ONLY:
                    keyword[param.parameter.name] = task
                else:
                    positional.append(task)

        positional_parameters = tuple(positional)
        keyword_parameters = tuple((k, v) for k, v in keyword.items())

        assert dep.call is not None
        tasks[dep.cache_key] = task = Task(
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
        ts.add(task, *(tasks[p.dependency.cache_key] for p in dag[dep]))
    return tasks
