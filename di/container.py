from __future__ import annotations

from collections import deque
from contextvars import ContextVar
from typing import (
    Any,
    Collection,
    ContextManager,
    Deque,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    Union,
    cast,
)

from di._utils.dag import topsort
from di._utils.execution_planning import SolvedDependantCache, plan_execution
from di._utils.inspect import is_async_gen_callable, is_coroutine_callable
from di._utils.nullcontext import nullcontext
from di._utils.state import ContainerState, LocalScopeContext
from di._utils.task import AsyncTask, SyncTask, Task
from di.exceptions import SolvingError
from di.executors import DefaultExecutor
from di.types import FusedContextManager
from di.types.dependencies import DependantBase, DependencyParameter
from di.types.executor import AsyncExecutor, SyncExecutor
from di.types.providers import (
    DependencyProvider,
    DependencyProviderType,
    DependencyType,
)
from di.types.scopes import Scope
from di.types.solved import SolvedDependant

Dependency = Any

_DependantDag = Dict[DependantBase[Any], Set[DependantBase[Any]]]
_DependantTaskDag = Dict[Task[Any], Set[Task[Any]]]
_DependantQueue = Deque[DependantBase[Any]]


class Container:
    _context: ContextVar[ContainerState]
    _executor: Union[AsyncExecutor, SyncExecutor]

    def __init__(
        self,
        *,
        execution_scope: Scope = None,
        executor: Optional[Union[AsyncExecutor, SyncExecutor]] = None,
    ) -> None:
        self._context = ContextVar("context")
        state = ContainerState()
        self._context.set(state)
        self._executor = executor or DefaultExecutor()
        self._execution_scope = execution_scope

    @property
    def _state(self) -> ContainerState:
        return self._context.get()

    @property
    def scopes(self) -> Collection[Scope]:
        return self._state.scopes

    def enter_global_scope(self, scope: Scope) -> FusedContextManager[None]:
        """Enter a global scope that is share amongst threads and coroutines.

        If you enter a global scope in one thread / coroutine, it will propagate to others.
        """
        return self._state.enter_scope(scope)

    def enter_local_scope(self, scope: Scope) -> FusedContextManager[None]:
        """Enter a local scope that is localized to the current thread or coroutine.

        If you enter a local scope in one thread / coroutine, it will NOT propagate to others.
        """
        return LocalScopeContext(self._context, scope)

    def bind(
        self,
        provider: DependantBase[DependencyType],
        dependency: DependencyProviderType[DependencyType],
    ) -> ContextManager[None]:
        """Bind a new dependency provider for a given dependency.

        This can be used as a function (for a permanent bind, cleared when `scope` is exited)
        or as a context manager (the bind will be cleared when the context manager exits).

        Binds are only identified by the identity of the callable and do not take into account
        the scope or any other data from the dependency they are replacing.
        """
        return self._state.bind(provider=provider, dependency=dependency)

    @property
    def binds(self) -> Mapping[DependencyProvider, DependantBase[Any]]:
        return self._state.binds

    def solve(
        self,
        dependency: DependantBase[DependencyType],
    ) -> SolvedDependant[DependencyType]:
        """Solve a dependency.

        Returns a SolvedDependant that can be executed to get the dependency's value.
        """

        # If the SolvedDependant itself is a bind, replace it's dependant
        if dependency.call in self._state.binds:
            dependency = self._state.binds[dependency.call]

        # Mapping of already seen dependants to itself for hash based lookups
        dep_registry: Dict[DependantBase[Any], DependantBase[Any]] = {}

        # DAG mapping dependants to their dependendencies
        dep_dag: Dict[DependantBase[Any], List[DependantBase[Any]]] = {}

        # The same DAG as above but including parameters (inspect.Parameter instances)
        param_graph: Dict[
            DependantBase[Any],
            List[DependencyParameter[DependantBase[Any]]],
        ] = {}

        def get_params(
            dep: DependantBase[Any],
        ) -> List[DependencyParameter[DependantBase[Any]]]:
            # get parameters and swap them out w/ binds when they
            # exist as a bound value
            params = dep.get_dependencies().copy()
            for idx, param in enumerate(params):
                assert param.dependency.call is not None
                if param.dependency.call in self._state.binds:
                    params[idx] = DependencyParameter[Any](
                        dependency=self._state.binds[param.dependency.call],
                        parameter=param.parameter,
                    )
            return params

        def check_equivalent(dep: DependantBase[Any]) -> None:
            if dep in dep_registry and dep.scope != dep_registry[dep].scope:
                raise SolvingError(
                    f"The dependencies {dep} and {dep_registry[dep]}"
                    " have the same lookup (__hash__ and __eq__) but have different scopes"
                    f" ({dep.scope} and {dep_registry[dep].scope} respectively)"
                    " This is likely a mistake, but you can override this behavior by either:"
                    "\n  1. Wrapping the function in another function or subclassing the class such"
                    " that they now are considered different dependencies"
                    "\n  2. Use a custom implemetnation of DependantBase that changes the meaning"
                    " or computation of __hash__ and/or __eq__"
                )

        # Do a DFS of the DAG checking constraints along the way
        q: _DependantQueue = deque((dependency,))
        while q:
            dep = q.popleft()
            if dep in dep_registry:
                check_equivalent(dep)
            else:
                dep_registry[dep] = dep
                params = get_params(dep)
                param_graph[dep] = params
                dep_dag[dep] = []
                for param in params:
                    predecessor_dep = param.dependency
                    dep_dag[dep].append(predecessor_dep)
                    if predecessor_dep not in dep_registry:
                        q.append(predecessor_dep)
        # The whole concept of Tasks is something that can perhaps be cleaned up / optimized
        # The main reason to have it is to save some computation at runtime
        # but currently that is just checking if the dependendency is sync or async
        # So perhaps that can be done in a simpler manner
        tasks = self._build_tasks(param_graph, topsort(dep_dag))
        dependency_dag: _DependantDag = {
            dep: set(predecessor_deps) for dep, predecessor_deps in dep_dag.items()
        }
        task_dependency_dag: _DependantTaskDag = {
            tasks[dep]: {tasks[predecessor_dep] for predecessor_dep in predecessor_deps}
            for dep, predecessor_deps in dependency_dag.items()
        }
        task_dependant_dag: _DependantTaskDag = {tasks[dep]: set() for dep in dep_dag}
        for task, predecessor_tasks in task_dependency_dag.items():
            for predecessor_task in predecessor_tasks:
                task_dependant_dag[predecessor_task].add(task)
        container_cache = SolvedDependantCache(
            root_task=tasks[dependency],
            task_dependency_dag=task_dependency_dag,
            task_dependant_dag=task_dependant_dag,
        )
        solved = SolvedDependant(
            dependency=dependency,
            dag=param_graph,
            container_cache=container_cache,
        )
        # run plan to populate cache
        plan_execution(
            self._state,
            solved,
            execution_scope=self._execution_scope,
            validate_scopes=False,
        )
        return solved

    def _build_tasks(
        self,
        dag: Dict[
            DependantBase[Any],
            List[DependencyParameter[DependantBase[Any]]],
        ],
        topsorted: List[DependantBase[Any]],
    ) -> Dict[DependantBase[Any], Union[AsyncTask[Any], SyncTask[Any]]]:
        tasks: Dict[DependantBase[Any], Union[AsyncTask[Any], SyncTask[Any]]] = {}
        for dep in reversed(topsorted):
            task_dependencies: List[DependencyParameter[Task[Any]]] = [
                DependencyParameter(
                    dependency=tasks[param.dependency], parameter=param.parameter
                )
                for param in dag[dep]
            ]

            if is_async_gen_callable(dep.call) or is_coroutine_callable(dep.call):
                tasks[dep] = AsyncTask(dependant=dep, dependencies=task_dependencies)
            else:
                tasks[dep] = SyncTask(dependant=dep, dependencies=task_dependencies)
        return tasks

    def _update_cache(
        self,
        results: Dict[DependantBase[Any], Any],
        to_cache: Iterable[DependantBase[Any]],
    ) -> None:
        for dep in to_cache:
            self._state.cached_values.set(
                dep.call,  # type: ignore[arg-type]
                results[dep],
                scope=dep.scope,
            )

    def execute_sync(
        self,
        solved: SolvedDependant[DependencyType],
        *,
        validate_scopes: bool = True,
        values: Optional[Mapping[DependencyProvider, Any]] = None,
    ) -> DependencyType:
        """Execute an already solved dependency.

        This method is synchronous and uses a synchronous executor,
        but the executor may still be able to execute async dependencies.

        If you are not dynamically changing scopes, you can run once with `validate_scopes=True`
        and then disable scope validation in subsequent runs with `validate_scope=False`.
        """
        cm: FusedContextManager[None]
        if self._execution_scope in self.scopes:
            cm = nullcontext()
        else:
            cm = self.enter_local_scope(self._execution_scope)
        with cm:
            results, leaf_tasks, to_cache = plan_execution(
                self._state,
                solved,
                execution_scope=self._execution_scope,
                validate_scopes=validate_scopes,
                values=values,
            )
            if not hasattr(self._executor, "execute_sync"):  # pragma: no cover
                raise TypeError(
                    "execute_sync requires an executor implementing the SyncExecutor protocol"
                )
            executor = cast(SyncExecutor, self._executor)
            if leaf_tasks:
                executor.execute_sync(leaf_tasks)
            self._update_cache(results, to_cache)
            return results[solved.dependency]  # type: ignore[no-any-return]

    async def execute_async(
        self,
        solved: SolvedDependant[DependencyType],
        *,
        validate_scopes: bool = True,
        values: Optional[Mapping[DependencyProvider, Any]] = None,
    ) -> DependencyType:
        """Execute an already solved dependency.

        If you are not dynamically changing scopes, you can run once with `validate_scopes=True`
        and then disable scope validation in subsequent runs with `validate_scope=False`.
        """
        cm: FusedContextManager[None]
        if self._execution_scope in self.scopes:
            cm = nullcontext()
        else:
            cm = self.enter_local_scope(self._execution_scope)
        async with cm:
            results, leaf_tasks, to_cache = plan_execution(
                self._state,
                solved,
                execution_scope=self._execution_scope,
                validate_scopes=validate_scopes,
                values=values,
            )
            if not hasattr(self._executor, "execute_async"):  # pragma: no cover
                raise TypeError(
                    "execute_async requires an executor implementing the AsyncExecutor protocol"
                )
            executor = cast(AsyncExecutor, self._executor)
            if leaf_tasks:
                await executor.execute_async(leaf_tasks)
            self._update_cache(results, to_cache)
            return results[solved.dependency]  # type: ignore[no-any-return]
