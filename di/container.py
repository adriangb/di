from __future__ import annotations

import contextvars
from collections import defaultdict, deque
from contextlib import contextmanager
from types import TracebackType
from typing import (
    Any,
    Collection,
    ContextManager,
    DefaultDict,
    Deque,
    Dict,
    Generator,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
)

from di._utils.dag import topsort
from di._utils.execution_planning import SolvedDependantCache, plan_execution
from di._utils.inspect import is_async_gen_callable, is_coroutine_callable
from di._utils.nullcontext import nullcontext
from di._utils.state import ContainerState
from di._utils.task import AsyncTask, SyncTask, Task
from di._utils.types import FusedContextManager
from di.api.dependencies import DependantBase, DependencyParameter
from di.api.executor import AsyncExecutor, SyncExecutor
from di.api.providers import DependencyProvider, DependencyProviderType, DependencyType
from di.api.scopes import Scope
from di.api.solved import SolvedDependant
from di.exceptions import SolvingError
from di.executors import DefaultExecutor

Dependency = Any

_DependantDag = Dict[DependantBase[Any], Set[DependantBase[Any]]]
_DependantTaskDag = Dict[Task, Set[Task]]
_CallMap = DefaultDict[DependencyProvider, Set[Task]]
_DependantQueue = Deque[DependantBase[Any]]
_ExecutionCM = FusedContextManager[None]
_nullcontext = nullcontext(None)


__all__ = ("BaseContainer", "Container", "ContainerState")


class _ContainerCommon:
    __slots__ = ("_executor", "_execution_scope", "_binds")

    _executor: Union[SyncExecutor, AsyncExecutor]
    _execution_scope: Scope
    _binds: Dict[DependencyProvider, DependantBase[Any]]

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

        # Build tasks and SolvedDependency
        tasks = self._build_tasks(param_graph, topsort(dep_dag))
        dependency_dag: _DependantDag = {
            dep: set(predecessor_deps) for dep, predecessor_deps in dep_dag.items()
        }
        task_dependency_dag: _DependantTaskDag = {
            tasks[dep]: {tasks[predecessor_dep] for predecessor_dep in predecessor_deps}
            for dep, predecessor_deps in dependency_dag.items()
        }
        task_dependant_dag: _DependantTaskDag = {tasks[dep]: set() for dep in dep_dag}
        call_map: _CallMap = defaultdict(set)
        for task, predecessor_tasks in task_dependency_dag.items():
            call_map[task.call].add(task)
            for predecessor_task in predecessor_tasks:
                task_dependant_dag[predecessor_task].add(task)
        container_cache = SolvedDependantCache(
            root_task=tasks[dependency],
            task_dependency_dag=task_dependency_dag,
            task_dependant_dag=task_dependant_dag,
            cacheable_tasks={
                tasks[d]
                for d in dependency_dag
                if d.scope != self._execution_scope and d.share
            },
            cached_tasks={tasks[d] for d in dependency_dag if d.share},
            execution_plan=None,
            validated_scopes=set(),
            call_map=call_map,
        )
        solved = SolvedDependant(
            dependency=dependency,
            dag=param_graph,
            container_cache=container_cache,
        )
        return solved

    def _build_tasks(
        self,
        dag: Dict[
            DependantBase[Any],
            List[DependencyParameter],
        ],
        topsorted: List[DependantBase[Any]],
    ) -> Dict[DependantBase[Any], Union[AsyncTask, SyncTask]]:
        tasks: Dict[DependantBase[Any], Union[AsyncTask, SyncTask]] = {}
        for dep in reversed(topsorted):
            positional: List[Task] = []
            keyword: Dict[str, Task] = {}
            for param in dag[dep]:
                if param.parameter is not None:
                    task = tasks[param.dependency]
                    # prefer positional arguments since those can be unpacked from a generator
                    # saving generation of an intermediate dict
                    if param.parameter.kind is param.parameter.KEYWORD_ONLY:
                        keyword[param.parameter.name] = task
                    else:
                        positional.append(task)

            if is_async_gen_callable(dep.call) or is_coroutine_callable(dep.call):
                tasks[dep] = AsyncTask(
                    dependant=dep,
                    positional_parameters=positional,
                    keyword_parameters=keyword,
                )
            else:
                tasks[dep] = SyncTask(
                    dependant=dep,
                    positional_parameters=positional,
                    keyword_parameters=keyword,
                )
        return tasks

    def _update_cache(
        self,
        state: ContainerState,
        results: Dict[Task, Any],
        to_cache: Iterable[Task],
    ) -> None:
        cache = state.cached_values.set
        for task in to_cache:
            cache(
                task.dependant,
                results[task],
                scope=task.dependant.scope,
            )

    def execute_sync(
        self,
        solved: SolvedDependant[DependencyType],
        *,
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
            results, leaf_tasks, to_cache, root_task = plan_execution(
                stacks=state.stacks,
                cached_values=state.cached_values.to_mapping(),
                solved=solved,
                values=values,
            )
            if leaf_tasks:
                if not hasattr(self._executor, "execute_sync"):  # pragma: no cover
                    raise TypeError(
                        "execute_sync requires an executor implementing the SyncExecutor protocol"
                    )
                self._executor.execute_sync(leaf_tasks)  # type: ignore[union-attr]
            self._update_cache(state, results, to_cache)
            return results[root_task]  # type: ignore[no-any-return]

    async def execute_async(
        self,
        solved: SolvedDependant[DependencyType],
        *,
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
            results, leaf_tasks, to_cache, root_task = plan_execution(
                stacks=state.stacks,
                cached_values=state.cached_values.to_mapping(),
                solved=solved,
                values=values,
            )
            if leaf_tasks:
                if not hasattr(self._executor, "execute_async"):  # pragma: no cover
                    raise TypeError(
                        "execute_async requires an executor implementing the AsyncExecutor protocol"
                    )
                await self._executor.execute_async(leaf_tasks)  # type: ignore[union-attr]
            self._update_cache(state, results, to_cache)
            return results[root_task]  # type: ignore[no-any-return]


class BaseContainer(_ContainerCommon):
    """Basic container that lets you manage it's state yourself"""

    __slots__ = ("__state", "_tp")
    __state: ContainerState

    def __init__(
        self,
        *,
        execution_scope: Scope = None,
        executor: Optional[Union[AsyncExecutor, SyncExecutor]] = None,
        _state: Optional[ContainerState] = None,
        _binds: Optional[Dict[DependencyProvider, DependantBase[Any]]] = None,
    ) -> None:
        self._executor = executor or DefaultExecutor()
        self._execution_scope = execution_scope
        self.__state = _state or ContainerState.initialize()
        self._binds = _binds or {}

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
        new = self.__class__(
            execution_scope=self._execution_scope,
            executor=self._executor,
            _state=self.__state.copy(),  # cached values and scopes are not shared
            _binds=self._binds,  # binds are shared
        )
        return new

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
        _context: Optional[contextvars.ContextVar[ContainerState]] = None,
        _binds: Optional[Dict[DependencyProvider, DependantBase[Any]]] = None,
    ) -> None:
        if _context is None:
            self._context = contextvars.ContextVar(f"{self}._context")
            self._context.set(ContainerState.initialize())
        else:
            self._context = _context
        self._execution_scope = execution_scope
        self._executor = executor or DefaultExecutor()
        self._binds = _binds or {}

    @property
    def _state(self) -> ContainerState:
        return self._context.get()

    @property
    def scopes(self) -> Collection[Scope]:
        return self._state.stacks.keys()

    def copy(self: _ContainerType) -> _ContainerType:
        new = type(self)(
            execution_scope=self._execution_scope,
            executor=self._executor,
            _binds=self._binds,
            _context=self._context,
        )
        return new

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
