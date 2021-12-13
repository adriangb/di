from __future__ import annotations

import contextvars
from collections import deque
from contextlib import contextmanager
from types import TracebackType
from typing import (
    Any,
    Collection,
    ContextManager,
    Deque,
    Dict,
    Generator,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from graphlib2 import TopologicalSorter

from di._utils.execution_planning import SolvedDependantCache, plan_execution
from di._utils.inspect import is_async_gen_callable, is_coroutine_callable
from di._utils.nullcontext import nullcontext
from di._utils.state import ContainerState
from di._utils.task import AsyncTask, SyncTask
from di._utils.topsort import topsort
from di._utils.types import FusedContextManager
from di.api.dependencies import DependantBase, DependencyParameter
from di.api.executor import AsyncExecutor, SyncExecutor
from di.api.providers import DependencyProvider, DependencyProviderType
from di.api.scopes import Scope
from di.api.solved import SolvedDependant
from di.exceptions import SolvingError
from di.executors import DefaultExecutor

_Task = Union[AsyncTask, SyncTask]

_DependantTaskDag = Dict[_Task, Set[_Task]]
_DependantQueue = Deque[DependantBase[Any]]
_ExecutionCM = FusedContextManager[None]
_nullcontext = nullcontext(None)


DependencyType = TypeVar("DependencyType")


__all__ = ("BaseContainer", "Container")


class _ContainerCommon:
    __slots__ = ("_executor", "_execution_scope", "_binds")

    _executor: Union[SyncExecutor, AsyncExecutor]
    _execution_scope: Scope
    _binds: Dict[DependencyProvider, DependantBase[Any]]

    def __init__(
        self,
        executor: Union[SyncExecutor, AsyncExecutor],
        execution_scope: Scope,
        binds: Optional[Dict[DependencyProvider, DependantBase[Any]]],
    ):
        self._executor = executor
        self._execution_scope = execution_scope
        self._binds = binds or {}

    @property
    def binds(self) -> Mapping[DependencyProvider, DependantBase[Any]]:
        return self._binds

    @property
    def scopes(self) -> Collection[Scope]:
        return self._state.stacks.keys()

    @property
    def _state(self) -> ContainerState:
        raise NotImplementedError

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
        previous_provider = self.binds.get(dependency, None)

        self._binds[dependency] = provider

        @contextmanager
        def unbind() -> Generator[None, None, None]:
            try:
                yield
            finally:
                self._binds.pop(dependency)
                if previous_provider is not None:
                    self._binds[dependency] = previous_provider

        return unbind()

    def solve(
        self,
        dependency: DependantBase[DependencyType],
    ) -> SolvedDependant[DependencyType]:
        """Solve a dependency.

        Returns a SolvedDependant that can be executed to get the dependency's value.
        """
        # If the SolvedDependant itself is a bind, replace it's dependant
        if dependency.call in self._binds:
            dependency = self._binds[dependency.call]

        # Mapping of already seen dependants to itself for hash based lookups
        dep_registry: Dict[DependantBase[Any], DependantBase[Any]] = {}
        # DAG mapping dependants to their dependendencies
        dep_dag: Dict[DependantBase[Any], List[DependantBase[Any]]] = {}

        # The same DAG as above but including parameters (inspect.Parameter instances)
        param_graph: Dict[
            DependantBase[Any],
            List[DependencyParameter],
        ] = {}

        def get_params(
            dep: DependantBase[Any],
        ) -> List[DependencyParameter]:
            # get parameters and swap them out w/ binds when they
            # exist as a bound value
            params = dep.get_dependencies().copy()
            for idx, param in enumerate(params):
                assert param.dependency.call is not None
                if param.dependency.call in self._binds:
                    params[idx] = DependencyParameter(
                        dependency=self._binds[param.dependency.call],
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

        # Order the Dependant's topologically so that we can create Tasks
        # with references to all of their children
        dep_topsort = topsort(dep_dag)
        # Create a seperate TopologicalSorter to hold the Tasks
        ts: TopologicalSorter[_Task] = TopologicalSorter()
        tasks = self._build_tasks(
            param_graph, (node for nodes in dep_topsort for node in nodes), ts
        )
        for dep, predecessors in dep_dag.items():
            ts.add(tasks[dep], *(tasks[p] for p in predecessors))
        ts.prepare()
        task_dependency_dag: _DependantTaskDag = {
            tasks[dep]: {tasks[predecessor_dep] for predecessor_dep in predecessor_deps}
            for dep, predecessor_deps in dep_dag.items()
        }
        call_map: Dict[DependencyProvider, Set[_Task]] = {}
        for t in task_dependency_dag:
            if t.call not in call_map:
                call_map[t.call] = set()
            call_map[t.call].add(t)
        container_cache = SolvedDependantCache(
            root_task=tasks[dependency],
            topological_sorter=ts,
            cacheable_tasks={
                tasks[d]
                for d in dep_dag
                if d.scope != self._execution_scope and d.share
            },
            cached_tasks=tuple({(tasks[d], d.scope) for d in dep_dag if d.share}),
            validated_scopes=set(),
            call_map={k: tuple(v) for k, v in call_map.items()},
        )
        solved = SolvedDependant(
            dependency=dependency,
            dag=param_graph,
            topsort=dep_topsort,
            container_cache=container_cache,
        )
        return solved

    def _build_tasks(
        self,
        dag: Dict[
            DependantBase[Any],
            List[DependencyParameter],
        ],
        topsorted: Iterable[DependantBase[Any]],
        ts: TopologicalSorter[_Task],
    ) -> Dict[DependantBase[Any], _Task]:
        tasks: Dict[DependantBase[Any], _Task] = {}
        for dep in topsorted:
            positional: List[_Task] = []
            keyword: Dict[str, _Task] = {}
            for param in dag[dep]:
                if param.parameter is not None and param.dependency.call is not None:
                    task = tasks[param.dependency]
                    # prefer positional arguments since those can be unpacked from a generator
                    # saving generation of an intermediate dict
                    if param.parameter.kind is param.parameter.KEYWORD_ONLY:
                        keyword[param.parameter.name] = task
                    else:
                        positional.append(task)

            positional_parameters = tuple(positional)
            keyword_parameters = tuple((k, v) for k, v in keyword.items())

            if is_async_gen_callable(dep.call) or is_coroutine_callable(dep.call):
                tasks[dep] = task = AsyncTask(
                    dependant=dep,
                    positional_parameters=positional_parameters,
                    keyword_parameters=keyword_parameters,
                )
            else:
                tasks[dep] = task = SyncTask(
                    dependant=dep,
                    positional_parameters=positional_parameters,
                    keyword_parameters=keyword_parameters,
                )
            ts.add(task, *(tasks[p.dependency] for p in dag[dep]))
        return tasks

    def _update_cache(
        self,
        state: ContainerState,
        results: Dict[_Task, Any],
        to_cache: Iterable[Tuple[_Task, Scope]],
    ) -> None:
        cache = state.cached_values.set
        for task in to_cache:
            cache(
                task[0].dependant,
                results[task[0]],
                scope=task[1],
            )

    def execute_sync(
        self,
        solved: SolvedDependant[DependencyType],
        *,
        executor: Optional[SyncExecutor] = None,
        values: Optional[Mapping[DependencyProvider, Any]] = None,
    ) -> DependencyType:
        """Execute an already solved dependency.

        This method is synchronous and uses a synchronous executor,
        but the executor may still be able to execute async dependencies.
        """
        cm: _ExecutionCM
        state = self._state
        if self._execution_scope in state.stacks.keys():
            cm = _nullcontext
        else:
            state = state.copy()
            cm = state.enter_scope(self._execution_scope)
        with cm:
            results, leaf_tasks, execution_state, to_cache, root_task = plan_execution(
                stacks=state.stacks,
                cached_values=state.cached_values.to_mapping(),
                solved=solved,
                values=values,
            )
            if root_task not in results:
                (executor or self._executor).execute_sync(leaf_tasks, execution_state)  # type: ignore[union-attr]
                self._update_cache(state, results, to_cache)
            return results[root_task]  # type: ignore[no-any-return]

    async def execute_async(
        self,
        solved: SolvedDependant[DependencyType],
        *,
        executor: Optional[AsyncExecutor] = None,
        values: Optional[Mapping[DependencyProvider, Any]] = None,
    ) -> DependencyType:
        """Execute an already solved dependency."""
        cm: _ExecutionCM
        state = self._state
        if self._execution_scope in state.stacks.keys():
            cm = _nullcontext
        else:
            state = state.copy()
            cm = state.enter_scope(self._execution_scope)
        async with cm:
            results, leaf_tasks, execution_state, to_cache, root_task = plan_execution(
                stacks=state.stacks,
                cached_values=state.cached_values.to_mapping(),
                solved=solved,
                values=values,
            )
            if root_task not in results:
                await (executor or self._executor).execute_async(leaf_tasks, execution_state)  # type: ignore[union-attr]
                self._update_cache(state, results, to_cache)
            return results[root_task]  # type: ignore[no-any-return]


class BaseContainer(_ContainerCommon):
    """Basic container that lets you manage it's state yourself"""

    __slots__ = ("__state",)
    __state: ContainerState

    def __init__(
        self,
        *,
        execution_scope: Scope = None,
        executor: Optional[Union[AsyncExecutor, SyncExecutor]] = None,
    ) -> None:
        super().__init__(
            executor=executor or DefaultExecutor(),
            execution_scope=execution_scope,
            binds={},
        )
        self.__state = ContainerState.initialize()

    @property
    def binds(self) -> Mapping[DependencyProvider, DependantBase[Any]]:
        return self._binds

    @property
    def scopes(self) -> Collection[Scope]:
        return self.__state.stacks.keys()

    @property
    def _state(self) -> ContainerState:
        return self.__state

    def copy(self: _BaseContainerType) -> _BaseContainerType:
        new = object.__new__(self.__class__)
        new._execution_scope = self._execution_scope
        new._executor = self._executor
        # binds are shared
        new._binds = self._binds
        # cached values and scopes are not shared
        new.__state = self.__state.copy()
        return new  # type: ignore[no-any-return]

    def enter_scope(
        self: _BaseContainerType, scope: Scope
    ) -> FusedContextManager[_BaseContainerType]:
        """Enter a scope and get back a new BaseContainer in that scope"""
        new = self.copy()
        return _ContainerScopeContext(scope, new, new.__state)


_BaseContainerType = TypeVar("_BaseContainerType", bound=BaseContainer)


class _ContainerScopeContext(FusedContextManager[_BaseContainerType]):
    __slots__ = ("scope", "container", "state", "cm")
    cm: FusedContextManager[None]

    def __init__(
        self,
        scope: Scope,
        container: _BaseContainerType,
        state: ContainerState,
    ) -> None:
        self.scope = scope
        self.container = container
        self.state = state

    def __enter__(self) -> _BaseContainerType:
        self.cm = self.state.enter_scope(self.scope)
        self.cm.__enter__()
        return self.container

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        return self.cm.__exit__(exc_type, exc_value, traceback)

    async def __aenter__(self) -> _BaseContainerType:
        self.cm = self.state.enter_scope(self.scope)
        await self.cm.__aenter__()
        return self.container

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        return await self.cm.__aexit__(exc_type, exc_value, traceback)


class Container(_ContainerCommon):
    """A container that manages it's own state via ContextVars"""

    __slots__ = "_context"

    _context: contextvars.ContextVar[ContainerState]

    def __init__(
        self,
        *,
        execution_scope: Scope = None,
        executor: Optional[Union[AsyncExecutor, SyncExecutor]] = None,
    ) -> None:
        super().__init__(
            executor=executor or DefaultExecutor(),
            execution_scope=execution_scope,
            binds={},
        )
        self._context = contextvars.ContextVar(f"{self}._context")
        self._context.set(ContainerState.initialize())

    @property
    def _state(self) -> ContainerState:
        return self._context.get()

    @property
    def scopes(self) -> Collection[Scope]:
        return self._state.stacks.keys()

    def copy(self: _ContainerType) -> _ContainerType:
        new = object.__new__(self.__class__)
        new._execution_scope = self._execution_scope
        new._executor = self._executor
        new._binds = self._binds
        new._context = self._context
        return new  # type: ignore[no-any-return]

    def enter_scope(
        self: _ContainerType, scope: Scope
    ) -> FusedContextManager[_ContainerType]:
        new = self.copy()
        return _ContextVarStateManager(
            self._context, scope, new  # type: ignore[attr-defined]
        )


_ContainerType = TypeVar("_ContainerType", bound=Container)


class _ContextVarStateManager(FusedContextManager[_ContainerType]):
    __slots__ = ("scope", "container", "context", "cm", "token")

    cm: FusedContextManager[None]

    def __init__(
        self,
        context: contextvars.ContextVar[ContainerState],
        scope: Scope,
        container: _ContainerType,
    ) -> None:
        self.context = context
        self.scope = scope
        self.container = container

    def __enter__(self) -> _ContainerType:
        new_state = self.context.get().copy()
        self.cm = new_state.enter_scope(self.scope)
        self.cm.__enter__()
        self.token = self.context.set(new_state)
        return self.container

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        self.context.reset(self.token)
        return self.cm.__exit__(exc_type, exc_value, traceback)

    async def __aenter__(self) -> _ContainerType:
        new_state = self.context.get().copy()
        self.cm = new_state.enter_scope(self.scope)
        await self.cm.__aenter__()
        self.token = self.context.set(new_state)
        return self.container

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        self.context.reset(self.token)
        return await self.cm.__aexit__(exc_type, exc_value, traceback)
