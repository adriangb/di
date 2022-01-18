from __future__ import annotations

import contextvars
import inspect
import sys
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
    Sequence,
    Set,
    Type,
    TypeVar,
    Union,
)

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

from graphlib2 import TopologicalSorter

from di._utils.execution_planning import SolvedDependantCache, plan_execution
from di._utils.inspect import get_type, is_async_gen_callable, is_coroutine_callable
from di._utils.scope_validation import validate_scopes
from di._utils.state import ContainerState
from di._utils.task import AsyncTask, SyncTask
from di._utils.topsort import topsort
from di._utils.types import FusedContextManager
from di.api.dependencies import CacheKey, DependantBase, DependencyParameter
from di.api.executor import AsyncExecutorProtocol, SyncExecutorProtocol
from di.api.providers import DependencyProvider
from di.api.scopes import Scope
from di.api.solved import SolvedDependant
from di.exceptions import WiringError

__all__ = ("BaseContainer", "Container")


_Task = Union[AsyncTask, SyncTask]

_DependantTaskDag = Dict[_Task, Set[_Task]]
_DependantQueue = Deque[DependantBase[Any]]


DependencyType = TypeVar("DependencyType")


class RegisterHook(Protocol):
    def __call__(
        self, param: Optional[inspect.Parameter], dependant: DependantBase[Any]
    ) -> Optional[DependantBase[Any]]:
        ...


class _ContainerCommon:
    __slots__ = ("_scopes", "_register_hooks")

    _scopes: Sequence[Scope]
    _register_hooks: List[RegisterHook]

    def __init__(
        self,
        scopes: Sequence[Scope],
    ):
        self._scopes = list(scopes)
        self._register_hooks = []

    @property
    def scopes(self) -> Collection[Scope]:
        return self._state.stacks.keys()

    @property
    def _state(self) -> ContainerState:
        raise NotImplementedError

    def register(
        self,
        hook: RegisterHook,
    ) -> ContextManager[None]:
        """Replace a dependency provider with a new one.

        This can be used as a function (for a permanent bind, cleared when `scope` is exited)
        or as a context manager (the bind will be cleared when the context manager exits).

        Binds are only identified by the identity of the callable and do not take into account
        the scope or any other data from the dependency they are replacing.
        """

        self._register_hooks.append(hook)

        @contextmanager
        def unbind() -> Generator[None, None, None]:
            try:
                yield
            finally:
                self._register_hooks.remove(hook)

        return unbind()

    def register_by_type(
        self,
        provider: DependantBase[Any],
        dependency: DependencyProvider,
    ) -> ContextManager[None]:
        def hook(
            param: Optional[inspect.Parameter], dependant: DependantBase[Any]
        ) -> Optional[DependantBase[Any]]:
            if dependant.call is dependency:
                return provider
            if param is None:
                return None
            type_annotation_option = get_type(param)
            if type_annotation_option is None:
                return None
            type_annotation = type_annotation_option.value
            if type_annotation is dependency:
                return provider
            return None

        return self.register(hook)

    def solve(
        self,
        dependency: DependantBase[DependencyType],
    ) -> SolvedDependant[DependencyType]:
        """Solve a dependency.

        Returns a SolvedDependant that can be executed to get the dependency's value.
        """
        # If the dependency itself is a bind, replace it
        for hook in self._register_hooks:
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
                if param.parameter is not None:
                    param = param._replace(
                        dependency=param.dependency.register_parameter(param.parameter)
                    )
                for hook in self._register_hooks:
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
        q: _DependantQueue = deque((dependency,))
        while q:
            dep = q.popleft()
            cache_key = dep.cache_key
            if cache_key in dependants:
                continue
            else:
                dependants[cache_key] = dep
                params = get_params(dep)
                param_graph[dep] = params
                dep_dag[dep] = []
                for param in params:
                    predecessor_dep = param.dependency
                    dep_dag[dep].append(predecessor_dep)
                    if predecessor_dep not in dependants:
                        q.append(predecessor_dep)
        # Filter out any dependencies that do not have a call
        # These do not become tasks since they don't need to be computed
        computable_param_graph = {
            dep: [
                param for param in param_graph[dep] if param.dependency.call is not None
            ]
            for dep in param_graph
            if dep.call is not None
        }
        # Order the Dependant's topologically so that we can create Tasks
        # with references to all of their children
        dep_topsort = topsort(
            {
                dep.cache_key: [p.dependency.cache_key for p in params]
                for dep, params in computable_param_graph.items()
            }
        )
        # Create a seperate TopologicalSorter to hold the Tasks
        ts: TopologicalSorter[_Task] = TopologicalSorter()
        tasks = self._build_tasks(
            computable_param_graph,
            (dependants[key] for key_group in dep_topsort for key in key_group),
            ts,
        )
        ts.prepare()
        task_dependency_dag: _DependantTaskDag = {
            tasks[dep.cache_key]: {
                tasks[predecessor_dep.dependency.cache_key]
                for predecessor_dep in predecessor_deps
            }
            for dep, predecessor_deps in computable_param_graph.items()
        }
        call_map: Dict[DependencyProvider, Set[_Task]] = {}
        for t in task_dependency_dag:
            if t.call not in call_map:
                call_map[t.call] = set()
            call_map[t.call].add(t)
        container_cache = SolvedDependantCache(
            root_task=tasks[dependency.cache_key],
            topological_sorter=ts,
            callable_to_task_mapping={k: tuple(v) for k, v in call_map.items()},
        )
        validate_scopes(
            self._scopes,
            dep_dag,
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
        topsorted: Iterable[DependantBase[Any]],
        ts: TopologicalSorter[_Task],
    ) -> Dict[CacheKey, _Task]:
        tasks: Dict[CacheKey, _Task] = {}
        task_id = 0
        for dep in topsorted:
            positional: List[_Task] = []
            keyword: Dict[str, _Task] = {}
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
            if is_async_gen_callable(dep.call) or is_coroutine_callable(dep.call):
                tasks[dep.cache_key] = task = AsyncTask(
                    scope=dep.scope,
                    call=dep.call,
                    use_cache=dep.share,
                    dependant=dep,
                    task_id=task_id,
                    positional_parameters=positional_parameters,
                    keyword_parameters=keyword_parameters,
                )
            else:
                tasks[dep.cache_key] = task = SyncTask(
                    scope=dep.scope,
                    call=dep.call,
                    use_cache=dep.share,
                    dependant=dep,
                    task_id=task_id,
                    positional_parameters=positional_parameters,
                    keyword_parameters=keyword_parameters,
                )
            task_id += 1
            ts.add(task, *(tasks[p.dependency.cache_key] for p in dag[dep]))
        return tasks

    def execute_sync(
        self,
        solved: SolvedDependant[DependencyType],
        executor: SyncExecutorProtocol,
        *,
        values: Optional[Mapping[DependencyProvider, Any]] = None,
    ) -> DependencyType:
        """Execute an already solved dependency.

        This method is synchronous and uses a synchronous executor,
        but the executor may still be able to execute async dependencies.
        """
        results, leaf_tasks, execution_state, root_task = plan_execution(
            stacks=self._state.stacks,
            cache=self._state.cached_values,
            solved=solved,
            values=values,
        )
        if root_task.task_id not in results:
            executor.execute_sync(leaf_tasks, execution_state)  # type: ignore[union-attr]
        return results[root_task.task_id]  # type: ignore[no-any-return]

    async def execute_async(
        self,
        solved: SolvedDependant[DependencyType],
        executor: AsyncExecutorProtocol,
        *,
        values: Optional[Mapping[DependencyProvider, Any]] = None,
    ) -> DependencyType:
        """Execute an already solved dependency."""
        results, leaf_tasks, execution_state, root_task = plan_execution(
            stacks=self._state.stacks,
            cache=self._state.cached_values,
            solved=solved,
            values=values,
        )
        if root_task.task_id not in results:
            await executor.execute_async(leaf_tasks, execution_state)  # type: ignore[union-attr]
        return results[root_task.task_id]  # type: ignore[no-any-return]


class BaseContainer(_ContainerCommon):
    """Basic container that lets you manage it's state yourself"""

    __slots__ = ("__state",)
    __state: ContainerState

    def __init__(
        self,
        *,
        scopes: Sequence[Scope],
    ) -> None:
        super().__init__(
            scopes=scopes,
        )
        self.__state = ContainerState.initialize()

    @property
    def scopes(self) -> Collection[Scope]:
        return self.__state.stacks.keys()

    @property
    def _state(self) -> ContainerState:
        return self.__state

    def copy(self: _BaseContainerType) -> _BaseContainerType:
        new = object.__new__(self.__class__)
        new._scopes = self._scopes
        # binds are shared
        new._register_hooks = self._register_hooks
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
        scopes: Sequence[Scope],
    ) -> None:
        super().__init__(
            scopes=scopes,
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
        new._scopes = self._scopes
        new._register_hooks = self._register_hooks
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
