from __future__ import annotations

from collections import deque
from contextlib import ExitStack, asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from types import TracebackType
from typing import (
    Any,
    AsyncContextManager,
    Callable,
    ContextManager,
    Deque,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    cast,
)

from di._inspect import (
    DependencyParameter,
    is_async_gen_callable,
    is_coroutine_callable,
    is_gen_callable,
)
from di._state import ContainerState
from di._task import AsyncTask, SyncTask, Task
from di._topsort import topsort
from di.exceptions import (
    DependencyRegistryError,
    DuplicateScopeError,
    IncompatibleDependencyError,
    ScopeViolationError,
    UnknownScopeError,
)
from di.executors import DefaultExecutor
from di.types import FusedContextManager
from di.types.dependencies import DependantProtocol
from di.types.executor import AsyncExecutor, SyncExecutor
from di.types.providers import (
    AsyncGeneratorProvider,
    CallableProvider,
    CoroutineProvider,
    Dependency,
    DependencyProvider,
    DependencyProviderType,
    DependencyType,
    GeneratorProvider,
)
from di.types.scopes import Scope


@dataclass
class SolvedDependency(Generic[DependencyType]):
    """Representation of a fully solved dependency.

    A fully solved dependency consists of:
    - A DAG of sub-dependency paramters.
    - A topologically sorted order of execution, where each sublist represents a
    group of dependencies that can be executed in parallel.
    """

    dependency: DependantProtocol[DependencyType]
    dag: Dict[
        DependantProtocol[Any], Dict[str, DependencyParameter[DependantProtocol[Any]]]
    ]
    topsort: List[List[DependantProtocol[Any]]]


class Container:
    def __init__(
        self, executor: Optional[Union[AsyncExecutor, SyncExecutor]] = None
    ) -> None:
        self._context = ContextVar[ContainerState]("context")
        state = ContainerState()
        state.cached_values.add_scope("container")
        state.cached_values.set(Container, self, scope="container")
        self._context.set(state)
        self._executor: Union[AsyncExecutor, SyncExecutor] = (
            executor or DefaultExecutor()
        )

    @property
    def _state(self) -> ContainerState:
        return self._context.get()

    def enter_global_scope(self, scope: Scope) -> FusedContextManager[None]:
        """Enter a global scope that is shared amongst threads and coroutines.

        If you enter a global scope in one thread / coroutine, it will propagate to others.
        """
        return self._state.enter_scope(scope)

    def enter_local_scope(self, scope: Scope) -> FusedContextManager[None]:
        """Enter a local scope that is localized to the current thread or coroutine.

        If you enter a global scope in one thread / coroutine, it will NOT propagate to others.
        """
        if scope in self._state.stacks:
            raise DuplicateScopeError(f"Scope {scope} has already been entered!")

        container = self

        class LocalScopeContext(FusedContextManager[None]):
            def __enter__(self):
                current = container._state
                new = current.copy()
                self.token = container._context.set(new)
                self.state_cm = cast(ContextManager[None], new.enter_scope(scope))
                self.state_cm.__enter__()

            def __exit__(
                self,
                exc_type: Optional[Type[BaseException]],
                exc_value: Optional[BaseException],
                traceback: Optional[TracebackType],
            ) -> Union[None, bool]:
                container._context.reset(self.token)
                cm = cast(ContextManager[None], self.state_cm)
                return cm.__exit__(exc_type, exc_value, traceback)

            async def __aenter__(self):
                current = container._state
                new = current.copy()
                self.token = container._context.set(new)
                self.state_cm = cast(AsyncContextManager[None], new.enter_scope(scope))
                await self.state_cm.__aenter__()

            async def __aexit__(
                self,
                exc_type: Optional[Type[BaseException]],
                exc_value: Optional[BaseException],
                traceback: Optional[TracebackType],
            ) -> Union[None, bool]:
                container._context.reset(self.token)
                cm = cast(AsyncContextManager[None], self.state_cm)
                return await cm.__aexit__(exc_type, exc_value, traceback)

        return LocalScopeContext()

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
        self, dependency: DependantProtocol[DependencyType]
    ) -> SolvedDependency[DependencyType]:
        """Solve a dependency.

        This is done automatically when calling `execute`, but you can store the returned value
        from this function and call `execute_solved` instead if you know that your binds
        will not be changing between calls.
        """

        if dependency.call in self._state.binds:  # type: ignore
            dependency = self._state.binds[dependency.call]  # type: ignore

        param_graph: Dict[
            DependantProtocol[Any],
            Dict[str, DependencyParameter[DependantProtocol[Any]]],
        ] = {}

        dep_registry: Dict[DependantProtocol[Any], DependantProtocol[Any]] = {}

        dep_dag: Dict[DependantProtocol[Any], List[DependantProtocol[Any]]] = {}

        def get_params(
            dep: DependantProtocol[Any],
        ) -> Dict[str, DependencyParameter[DependantProtocol[Any]]]:
            params = dep.get_dependencies().copy()
            for keyword, param in params.items():
                assert param.dependency.call is not None
                if param.dependency.call in self._state.binds:
                    params[keyword] = DependencyParameter[Any](
                        dependency=self._state.binds.get(param.dependency.call),
                        parameter=param.parameter,
                    )
            return params

        def check_equivalent(dep: DependantProtocol[Any]):
            if not dep.is_equivalent(dep_registry[dep]):
                raise DependencyRegistryError(
                    f"The dependencies {dep} and {dep_registry[dep]}"
                    " have the same hash but are not equal."
                    " This can be caused by using the same callable / class as a dependency in"
                    " two different scopes, which is usually a mistake"
                    " To work around this, you can subclass or wrap the function so that it"
                    " does not have the same hash/id."
                    " Alternatively, you may provide an implementation of DependencyProtocol"
                    " that uses custom __hash__ and __eq__ semantics."
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
                for param in params.values():
                    subdep = param.dependency
                    dep_dag[dep].append(subdep)
                    if subdep not in dep_registry:
                        q.append(subdep)

        groups = topsort(dependency, dep_dag)
        return SolvedDependency[DependencyType](
            dependency=dependency, dag=param_graph, topsort=groups
        )

    def get_flat_subdependants(
        self, solved: SolvedDependency[Any]
    ) -> List[DependantProtocol[Any]]:
        """Get an exhaustive list of all of the dependencies of this dependency,
        in no particular order.
        """
        return [dep for group in solved.topsort[1:] for dep in group]

    def _build_task(
        self,
        dependency: DependantProtocol[DependencyType],
        tasks: Dict[
            DependantProtocol[Any], Union[AsyncTask[Dependency], SyncTask[Dependency]]
        ],
        state: ContainerState,
        dag: Dict[
            DependantProtocol[Any],
            Dict[str, DependencyParameter[DependantProtocol[Any]]],
        ],
    ) -> Union[AsyncTask[DependencyType], SyncTask[DependencyType]]:

        task_dependencies: Dict[str, DependencyParameter[Task[DependencyProvider]]] = {}

        for param_name, param in dag[dependency].items():
            task_dependencies[param_name] = DependencyParameter(
                dependency=tasks[param.dependency], parameter=param.parameter
            )

        if is_async_gen_callable(dependency.call) or is_coroutine_callable(
            dependency.call
        ):

            async def async_call(*args: Any, **kwargs: Any) -> DependencyType:
                assert dependency.call is not None
                if dependency.shared and state.cached_values.contains(dependency.call):
                    # use cached value
                    res = state.cached_values.get(dependency.call)
                else:
                    if is_coroutine_callable(dependency.call):
                        res = await cast(
                            CoroutineProvider[DependencyType], dependency.call
                        )(*args, **kwargs)
                    else:
                        stack = state.stacks[dependency.scope]
                        if isinstance(stack, ExitStack):
                            raise IncompatibleDependencyError(
                                f"The dependency {dependency} is an awaitable dependency"
                                f" and canot be used in the sync scope {dependency.scope}"
                            )
                        res = await stack.enter_async_context(
                            asynccontextmanager(
                                cast(
                                    AsyncGeneratorProvider[DependencyType],
                                    dependency.call,
                                )
                            )(*args, **kwargs)
                        )
                    if dependency.shared:
                        # caching is allowed, now that we have a value we can save it and start using the cache
                        state.cached_values.set(
                            dependency.call, res, scope=dependency.scope
                        )

                return cast(DependencyType, res)

            return AsyncTask[DependencyType](
                call=async_call, dependencies=task_dependencies
            )
        else:
            # sync
            def sync_call(*args: Any, **kwargs: Any) -> DependencyType:
                assert dependency.call is not None
                if dependency.shared and state.cached_values.contains(dependency.call):
                    # use cached value
                    res = state.cached_values.get(dependency.call)
                else:
                    if not is_gen_callable(dependency.call):
                        res = cast(CallableProvider[DependencyType], dependency.call)(
                            *args, **kwargs
                        )
                    else:
                        stack = state.stacks[dependency.scope]
                        res = stack.enter_context(
                            contextmanager(
                                cast(GeneratorProvider[DependencyType], dependency.call)
                            )(*args, **kwargs)
                        )
                    if dependency.shared:
                        # caching is allowed, now that we have a value we can save it and start using the cache
                        state.cached_values.set(
                            dependency.call, res, scope=dependency.scope
                        )

                return cast(DependencyType, res)

            return SyncTask[DependencyType](
                call=sync_call, dependencies=task_dependencies
            )

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
            for param in params.values():
                subdep = param.dependency
                check_scope(subdep)
                check_is_inner(dep, subdep)

    def _build_tasks(
        self, solved: SolvedDependency[DependencyType]
    ) -> Tuple[
        List[List[Union[AsyncTask[Dependency], SyncTask[Dependency]]]],
        Callable[[], DependencyType],
    ]:
        tasks: Dict[
            DependantProtocol[Any], Union[AsyncTask[Dependency], SyncTask[Dependency]]
        ] = {}
        for group in reversed(solved.topsort):
            for dep in group:
                if dep not in tasks:
                    tasks[dep] = self._build_task(dep, tasks, self._state, solved.dag)
        get_result = tasks[solved.dependency].get_result
        return [[tasks[dep] for dep in group] for group in solved.topsort], get_result

    def execute_sync(
        self,
        solved: SolvedDependency[DependencyType],
        validate_scopes: bool = True,
    ) -> DependencyType:
        """Execute an already solved dependency.

        If you are not dynamically changing scopes, you can run once with `validate_scopes=True`
        and then disable scope validation in subsequent runs with `validate_scope=False`.
        """
        with self.enter_local_scope(None):
            if validate_scopes:
                self._validate_scopes(solved)

            tasks, get_result = self._build_tasks(solved)

            if not hasattr(self._executor, "execute_sync"):
                raise TypeError(
                    "execute_sync requires an executor implementing the SyncExecutor protocol"
                )
            executor = cast(SyncExecutor, self._executor)

            return executor.execute_sync(
                [[t.compute for t in group] for group in reversed(tasks)], get_result
            )

    async def execute_async(
        self,
        solved: SolvedDependency[DependencyType],
        validate_scopes: bool = True,
    ) -> DependencyType:
        """Execute an already solved dependency.

        If you are not dynamically changing scopes, you can run once with `validate_scopes=True`
        and then disable scope validation in subsequent runs with `validate_scope=False`.
        """
        async with self.enter_local_scope(None):
            if validate_scopes:
                self._validate_scopes(solved)

            tasks, get_result = self._build_tasks(solved)

            if not hasattr(self._executor, "execute_async"):
                raise TypeError(
                    "execute_async requires an executor implementing the AsyncExecutor protocol"
                )
            executor = cast(AsyncExecutor, self._executor)

            return await executor.execute_async(
                [[t.compute for t in group] for group in reversed(tasks)], get_result
            )
