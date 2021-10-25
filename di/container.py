from __future__ import annotations

import functools
from collections import deque
from contextvars import ContextVar
from dataclasses import dataclass
from typing import (
    Any,
    ContextManager,
    Deque,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Set,
    Tuple,
    Union,
    cast,
)

from di._dag import topsort
from di._inspect import is_async_gen_callable, is_coroutine_callable
from di._local_scope_context import LocalScopeContext
from di._nullcontext import nullcontext
from di._state import ContainerState
from di._task import AsyncTask, ExecutionState, SyncTask, Task
from di.exceptions import (
    DependencyRegistryError,
    DuplicateScopeError,
    ScopeViolationError,
    UnknownScopeError,
)
from di.executors import DefaultExecutor
from di.types import FusedContextManager
from di.types.dependencies import DependantProtocol, DependencyParameter
from di.types.executor import AsyncExecutor, SyncExecutor
from di.types.executor import Task as ExecutorTask
from di.types.providers import (
    DependencyProvider,
    DependencyProviderType,
    DependencyType,
)
from di.types.scopes import Scope
from di.types.solved import SolvedDependency

Dependency = Any


class _ExecutionPlanCache(NamedTuple):
    cache_key: FrozenSet[DependantProtocol[Any]]
    dependant_dag: Mapping[DependantProtocol[Any], Iterable[Task[Any]]]
    dependency_counts: Dict[DependantProtocol[Any], int]
    leaf_tasks: Iterable[Task[Any]]


@dataclass
class _SolvedDependencyCache:
    tasks: Mapping[DependantProtocol[Any], Task[Any]]
    dependency_dag: Mapping[DependantProtocol[Any], Set[DependantProtocol[Any]]]
    execution_plan: Optional[_ExecutionPlanCache] = None


class Container:
    _context: ContextVar[ContainerState]
    _executor: Union[AsyncExecutor, SyncExecutor]

    def __init__(
        self,
        *,
        default_scope: Scope = None,
        executor: Optional[Union[AsyncExecutor, SyncExecutor]] = None,
    ) -> None:
        self._context = ContextVar("context")
        state = ContainerState()
        state.cached_values.add_scope("container")
        state.cached_values.set(Container, self, scope="container")
        self._context.set(state)
        self._executor = executor or DefaultExecutor()
        self._default_scope = default_scope

    @property
    def _state(self) -> ContainerState:
        return self._context.get()

    @property
    def scopes(self) -> List[Scope]:
        return self._state.scopes

    def enter_global_scope(self, scope: Scope) -> FusedContextManager[None]:
        """Enter a global scope that is share amongst threads and coroutines.

        If you enter a global scope in one thread / coroutine, it will propagate to others.
        """
        return self._state.enter_scope(scope)

    def enter_local_scope(self, scope: Scope) -> FusedContextManager[None]:
        """Enter a local scope that is localized to the current thread or coroutine.

        If you enter a global scope in one thread / coroutine, it will NOT propagate to others.
        """
        if scope in self._state.stacks:
            raise DuplicateScopeError(f"Scope {scope} has already been entered!")
        return LocalScopeContext(self._context, scope)

    def bind(
        self,
        provider: DependantProtocol[DependencyType],
        dependency: DependencyProviderType[DependencyType],
    ) -> ContextManager[None]:
        """Bind a new dependency provider for a given dependency.

        This can be used as a function (for a permanent bind, cleared when `scope` is exited)
        or as a context manager (the bind will be cleared when the context manager exits).

        Binds are only identified by the identity of the callable and do not take into account
        the scope or any other data from the dependency they are replacing.

        The `scope` parameter determines the scope for the bind itself.
        The bind will be automatically cleared when that scope is exited.
        If no scope is provided, the current scope is used.
        """
        return self._state.bind(provider=provider, dependency=dependency)

    def solve(
        self,
        dependency: DependantProtocol[DependencyType],
    ) -> SolvedDependency[DependencyType]:
        """Solve a dependency.

        Returns a SolvedDependency that can be executed to get the dependency's value.

        The `siblings` paramter can be used to pass additional dependencies that should be executed
        that aren't strictly needed to solve `dependency`.
        """

        if dependency.call in self._state.binds:
            dependency = self._state.binds[dependency.call]

        param_graph: Dict[
            DependantProtocol[Any],
            List[DependencyParameter[DependantProtocol[Any]]],
        ] = {}

        dep_registry: Dict[DependantProtocol[Any], DependantProtocol[Any]] = {}

        dep_dag: Dict[DependantProtocol[Any], List[DependantProtocol[Any]]] = {}

        def get_params(
            dep: DependantProtocol[Any],
        ) -> List[DependencyParameter[DependantProtocol[Any]]]:
            params = dep.get_dependencies().copy()
            for idx, param in enumerate(params):
                assert param.dependency.call is not None
                if param.dependency.call in self._state.binds:
                    params[idx] = DependencyParameter[Any](
                        dependency=self._state.binds[param.dependency.call],
                        parameter=param.parameter,
                    )
            return params

        def check_equivalent(dep: DependantProtocol[Any]):
            if dep in dep_registry and dep.scope != dep_registry[dep].scope:
                raise DependencyRegistryError(
                    f"The dependencies {dep} and {dep_registry[dep]}"
                    " have the same lookup (__hash__ and __eq__) but have different scopes"
                    f" ({dep.scope} and {dep_registry[dep].scope} respectively)"
                    " This is likely a mistake, but you can override this behavior by either:"
                    "\n  1. Wrapping the function in another function or subclassing the class such"
                    " that they now are considered different dependencies"
                    "\n  2. Use a custom implemetnation of DependantProtocol that changes the meaning"
                    " or computation of __hash__ and/or __eq__"
                )

        q: Deque[DependantProtocol[Any]] = deque([dependency])
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
                    subdep = param.dependency
                    dep_dag[dep].append(subdep)
                    if subdep not in dep_registry:
                        q.append(subdep)
        tasks = self._build_tasks(param_graph, topsort(dep_dag))
        dependency_dag = {dep: set(subdeps) for dep, subdeps in dep_dag.items()}
        container_cache = _SolvedDependencyCache(
            dependency_dag=dependency_dag, tasks=tasks
        )
        return SolvedDependency(
            dependency=dependency,
            dag=param_graph,
            container_cache=container_cache,
        )

    def _build_tasks(
        self,
        dag: Dict[
            DependantProtocol[Any],
            List[DependencyParameter[DependantProtocol[Any]]],
        ],
        topsorted: List[DependantProtocol[Any]],
    ) -> Dict[DependantProtocol[Any], Union[AsyncTask[Any], SyncTask[Any]]]:
        tasks: Dict[DependantProtocol[Any], Union[AsyncTask[Any], SyncTask[Any]]] = {}
        for dep in reversed(topsorted):
            tasks[dep] = self._build_task(dep, tasks, dag)
        return tasks

    def _build_task(
        self,
        dependency: DependantProtocol[Any],
        tasks: Dict[DependantProtocol[Any], Union[AsyncTask[Any], SyncTask[Any]]],
        dag: Dict[
            DependantProtocol[Any],
            List[DependencyParameter[DependantProtocol[Any]]],
        ],
    ) -> Union[AsyncTask[Any], SyncTask[Any]]:

        task_dependencies: List[DependencyParameter[Task[Any]]] = [
            DependencyParameter(
                dependency=tasks[param.dependency], parameter=param.parameter
            )
            for param in dag[dependency]
        ]

        if is_async_gen_callable(dependency.call) or is_coroutine_callable(
            dependency.call
        ):
            return AsyncTask(dependant=dependency, dependencies=task_dependencies)
        else:
            return SyncTask(dependant=dependency, dependencies=task_dependencies)

    def _validate_scopes(self, solved: SolvedDependency[Dependency]) -> None:
        """Validate that dependencies all have a valid scope and
        that dependencies only depend on outer scopes or their own scope.
        """
        scopes: Dict[Scope, int] = {
            scope: idx
            for idx, scope in enumerate(reversed(self._state.scopes + [None]))
        }

        def check_is_inner(
            dep: DependantProtocol[Any], subdep: DependantProtocol[Any]
        ) -> None:
            if scopes[dep.scope] > scopes[subdep.scope]:
                raise ScopeViolationError(
                    f"{dep} cannot depend on {subdep} because {subdep}'s"
                    f" scope ({subdep.scope}) is narrower than {dep}'s scope ({dep.scope})"
                )

        def check_scope(dep: DependantProtocol[Any]) -> None:
            if dep.scope not in scopes:
                raise UnknownScopeError(
                    f"Dependency{dep} has an unknown scope {dep.scope}."
                    f" Did you forget to enter the {dep.scope} scope?"
                )

        for dep, params in solved.dag.items():
            check_scope(dep)
            for param in params:
                subdep = param.dependency
                check_scope(subdep)
                check_is_inner(dep, subdep)

    def _prepare_execution(
        self,
        solved: SolvedDependency[Any],
        *,
        validate_scopes: bool = True,
        values: Optional[Mapping[DependencyProvider, Any]] = None,
    ) -> Tuple[
        _ExecutionPlanCache, Dict[DependantProtocol[Any], Any], List[ExecutorTask]
    ]:
        user_values = values or {}
        if validate_scopes:
            self._validate_scopes(solved)

        if type(solved.container_cache) is not _SolvedDependencyCache:
            raise TypeError(
                "This SolvedDependency was not created by this Container"
            )  # pragma: no cover

        solved_dependency_cache = solved.container_cache

        cache: Dict[DependencyProvider, Any] = {}
        for mapping in self._state.cached_values.mappings.values():
            cache.update(mapping)
        cache.update(user_values)

        results: Dict[DependantProtocol[Any], Any] = {}

        def use_cache(dep: DependantProtocol[Any]) -> bool:
            call = dep.call
            if call in cache:
                if call in user_values:
                    results[dep] = user_values[call]
                    return True
                elif dep.share:
                    results[dep] = cache[call]
                    return True
                else:
                    return False
            return False

        for dep in solved.dag:
            use_cache(dep)

        execution_plan_cache_key = frozenset(results.keys())

        execution_plan = solved.container_cache.execution_plan

        if (
            execution_plan is None
            or execution_plan.cache_key != execution_plan_cache_key
        ):
            # Build a DAG of Tasks that we actually need to execute
            # this allows us to prune subtrees that will come
            # from pre-computed values (values paramter or cache)
            unvisited = deque([solved.dependency])
            # Make DAG values a set to account for dependencies that depend on the the same
            # sub dependency in more than one param (`def func(a: A, a_again: A)`)
            dependency_counts: Dict[DependantProtocol[Any], int] = {}
            dependant_dag: Dict[DependantProtocol[Any], Deque[Task[Any]]] = {
                dep: deque() for dep in solved_dependency_cache.dependency_dag
            }
            while unvisited:
                dep = unvisited.pop()
                if dep in dependency_counts:
                    continue
                # task the dependency is cached or was provided by value
                # we don't need to compute it or any of it's dependencies
                if dep not in results:
                    # otherwise, we add it to our DAG and visit it's children
                    dependency_counts[dep] = 0
                    for subdep in solved_dependency_cache.dependency_dag[dep]:
                        if subdep not in results:
                            dependant_dag[subdep].append(
                                solved_dependency_cache.tasks[dep]
                            )
                            dependency_counts[dep] += 1
                            if subdep not in dependency_counts:
                                unvisited.append(subdep)

            solved.container_cache.execution_plan = (
                execution_plan
            ) = _ExecutionPlanCache(
                cache_key=execution_plan_cache_key,
                dependant_dag=dependant_dag,
                dependency_counts=dependency_counts,
                leaf_tasks=[
                    solved_dependency_cache.tasks[dep]
                    for dep, count in dependency_counts.items()
                    if count == 0
                ],
            )

        state = ExecutionState(
            container_state=self._state,
            results=results,
            dependency_counts=execution_plan.dependency_counts.copy(),
            dependants=execution_plan.dependant_dag,
        )

        return (
            execution_plan,
            results,
            [functools.partial(t.compute, state) for t in execution_plan.leaf_tasks],
        )

    def _update_cache(
        self, results: Dict[DependantProtocol[Any], Any], plan: _ExecutionPlanCache
    ) -> None:
        execution_scope = self.scopes[-1]
        for dep in plan.dependency_counts.keys():
            if dep.share and dep.scope != execution_scope:
                self._state.cached_values.set(
                    dep.call,  # type: ignore[arg-type]
                    results[dep],
                    scope=dep.scope,
                )

    def execute_sync(
        self,
        solved: SolvedDependency[DependencyType],
        *,
        validate_scopes: bool = True,
        values: Optional[Mapping[DependencyProvider, Any]] = None,
    ) -> DependencyType:
        """Execute an already solved dependency.

        If you are not dynamically changing scopes, you can run once with `validate_scopes=True`
        and then disable scope validation in subsequent runs with `validate_scope=False`.
        """
        cm: FusedContextManager[None]
        if self._default_scope in self.scopes:
            cm = nullcontext(None)
        else:
            cm = self.enter_local_scope(self._default_scope)
        with cm:
            plan, results, queue = self._prepare_execution(
                solved, validate_scopes=validate_scopes, values=values
            )
            if not hasattr(self._executor, "execute_sync"):
                raise TypeError(
                    "execute_sync requires an executor implementing the SyncExecutor protocol"
                )
            executor = cast(SyncExecutor, self._executor)
            if queue:
                executor.execute_sync(queue)

            res = results[solved.dependency]
            self._update_cache(results, plan)
            return res

    async def execute_async(
        self,
        solved: SolvedDependency[DependencyType],
        *,
        validate_scopes: bool = True,
        values: Optional[Mapping[DependencyProvider, Any]] = None,
    ) -> DependencyType:
        """Execute an already solved dependency.

        If you are not dynamically changing scopes, you can run once with `validate_scopes=True`
        and then disable scope validation in subsequent runs with `validate_scope=False`.
        """
        cm: FusedContextManager[None]
        if self._default_scope in self.scopes:
            cm = nullcontext(None)
        else:
            cm = self.enter_local_scope(self._default_scope)
        async with cm:
            plan, results, queue = self._prepare_execution(
                solved, validate_scopes=validate_scopes, values=values
            )
            if not hasattr(self._executor, "execute_async"):
                raise TypeError(
                    "execute_async requires an executor implementing the AsyncExecutor protocol"
                )
            executor = cast(AsyncExecutor, self._executor)
            if queue:
                await executor.execute_async(queue)
            res = results[solved.dependency]
            self._update_cache(results, plan)
            return res
