from __future__ import annotations

import inspect
import typing
from contextlib import AsyncExitStack, ExitStack, contextmanager
from types import TracebackType
from typing import (
    Any,
    ContextManager,
    Generator,
    Generic,
    Iterable,
    Mapping,
    Protocol,
    Sequence,
    TypeVar,
    cast,
)
from warnings import warn

from graphlib2 import TopologicalSorter

from di._task import (
    CachedAsyncContextManagerTask,
    CachedAsyncTask,
    CachedSyncContextManagerTask,
    CachedSyncTask,
    ExecutionState,
    NotCachedAsyncContextManagerTask,
    NotCachedAsyncTask,
    NotCachedSyncContextManagerTask,
    NotCachedSyncTask,
    Task,
)
from di._utils.inspect import (
    get_type,
    is_async_gen_callable,
    is_coroutine_callable,
    is_gen_callable,
)
from di._utils.scope_map import ScopeMap
from di._utils.types import CacheKey, FusedContextManager
from di.api.dependencies import DependencyParameter, DependentBase
from di.api.executor import (
    SupportsAsyncExecutor,
    SupportsSyncExecutor,
    SupportsTaskGraph,
)
from di.api.executor import Task as SupportsTask
from di.api.providers import DependencyProvider
from di.api.scopes import Scope
from di.exceptions import (
    DependencyCycleError,
    ScopeViolationError,
    SolvingError,
    UnknownScopeError,
    WiringError,
)


class BindHook(Protocol):
    def __call__(
        self, param: inspect.Parameter | None, dependent: DependentBase[Any]
    ) -> DependentBase[Any] | None:  # pragma: no cover
        ...


def bind_by_type(
    provider: DependentBase[Any],
    dependency: type,
    *,
    covariant: bool = False,
) -> BindHook:
    """Hook to substitute the matched dependency"""

    def hook(
        param: inspect.Parameter | None, dependent: DependentBase[Any]
    ) -> DependentBase[Any] | None:
        if dependent.call == dependency:
            return provider
        if param is None:
            return None
        type_annotation_option = get_type(param)
        if type_annotation_option is None:
            return None
        type_annotation = type_annotation_option.value
        if type_annotation == dependency:
            return provider
        if covariant:
            if inspect.isclass(type_annotation) and inspect.isclass(dependency):
                if dependency in type_annotation.__mro__:
                    return provider
        return None

    return hook


class ScopeState:
    __slots__ = ("cached_values", "stacks")

    def __init__(
        self,
        cached_values: ScopeMap[CacheKey, Any] | None = None,
        stacks: dict[Scope, AsyncExitStack | ExitStack] | None = None,
    ) -> None:
        self.cached_values = cached_values or ScopeMap()
        self.stacks = stacks or {}

    def enter_scope(self, scope: Scope) -> FusedContextManager[ScopeState]:
        """Enter a scope and get back a new ScopeState object that you can use to execute dependencies."""
        new = ScopeState(
            cached_values=ScopeMap(self.cached_values.copy()),
            stacks=self.stacks.copy(),
        )
        return ScopeContext(new, scope)


class ScopeContext(FusedContextManager[ScopeState]):
    __slots__ = ("state", "scope", "stack")
    stack: AsyncExitStack | ExitStack

    def __init__(self, state: ScopeState, scope: Scope) -> None:
        self.state = state
        self.scope = scope

    def __enter__(self) -> ScopeState:
        self.state.stacks[self.scope] = self.stack = ExitStack()
        self.state.cached_values.add_scope(self.scope)
        return self.state

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None | bool:
        return self.stack.__exit__(exc_type, exc_value, traceback)  # type: ignore[union-attr,no-any-return]

    async def __aenter__(self) -> ScopeState:
        self.state.stacks[self.scope] = self.stack = AsyncExitStack()
        self.state.cached_values.add_scope(self.scope)
        return self.state

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None | bool:
        return await self.stack.__aexit__(exc_type, exc_value, traceback)  # type: ignore[union-attr,no-any-return]


class TaskGraph:
    __slots__ = ("_uncopied_ts", "_copied_ts", "_static_order")
    _copied_ts: TopologicalSorter[Task] | None

    def __init__(
        self,
        ts: TopologicalSorter[Task],
        static_order: Iterable[Task],
    ) -> None:
        self._uncopied_ts = ts
        self._copied_ts = None
        self._static_order = static_order

    def get_ready(self) -> Iterable[Task]:
        if self._copied_ts is None:
            self._copied_ts = self._uncopied_ts.copy()
        return self._copied_ts.get_ready()

    def done(self, task: SupportsTask) -> None:
        if self._copied_ts is None:
            self._copied_ts = self._uncopied_ts.copy()
        self._copied_ts.done(cast(Task, task))

    def is_active(self) -> bool:
        if self._copied_ts is None:
            self._copied_ts = self._uncopied_ts.copy()
        return self._copied_ts.is_active()

    def static_order(self) -> Iterable[Task]:
        return self._static_order


EMPTY_VALUES: dict[DependencyProvider, Any] = {}


T = TypeVar("T")


POSITIONAL_PARAMS = (
    inspect.Parameter.POSITIONAL_ONLY,
    inspect.Parameter.POSITIONAL_OR_KEYWORD,
)


class ScopeResolver(Protocol):
    def __call__(
        self,
        __dependent: DependentBase[Any],
        __sub_dependenant_scopes: Sequence[Scope],
        __solver_scopes: Sequence[Scope],
    ) -> Scope:
        """Infer scopes for a Marker/Dependent that does not have an explicit scope.

        The three parameters given are:
        - `sub_dependenant_scopes`: the scopes of all sub-dependencies (if any).
          This can be used to set a lower bound for the scope.
          For example, if a sub dependency has some "singleton" scope
          our current dependency (the `dependent` argument) cannot have some "ephemeral"
          scope because that would violate scoping rules.
        - `solver_scopes`: the scopes passed to `Container.solve`. Provided for convenience.
        - `dependent`: the current dependency we are inferring a scope for.
        """


def get_path_str(path: Iterable[DependentBase[Any]]) -> str:
    return " -> ".join(
        [repr(item) if item.call is not None else repr(item.call) for item in path]
    )


def get_params(
    dep: DependentBase[Any],
    binds: Iterable[BindHook],
    path: Iterable[DependentBase[Any]],
) -> list[DependencyParameter]:
    """Get Dependents for parameters and resolve binds"""
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
    path: Iterable[DependentBase[Any]],
) -> None:
    if task.scope not in scopes:
        raise UnknownScopeError(
            f"Dependency{task.unwrapped_call} has an unknown scope {task.scope}."
            f"\nExample Path: {get_path_str(path)}"
        )
    for subtask in subtasks:
        if scopes[task.scope] < scopes[subtask.scope]:
            raise ScopeViolationError(
                f"{task.unwrapped_call} cannot depend on {subtask.unwrapped_call}"
                f" because {subtask.unwrapped_call}'s scope ({subtask.scope})"
                f" is narrower than {task.unwrapped_call}'s scope ({task.scope})"
                f"\nExample Path: {get_path_str(path)}"
            )


def build_task(  # noqa: C901
    dependency: DependentBase[Any],
    binds: Iterable[BindHook],
    tasks: dict[CacheKey, Task],
    task_dag: dict[Task, list[Task]],
    dependent_dag: dict[DependentBase[Any], list[DependencyParameter]],
    path: dict[DependentBase[Any], Any],
    scope_idxs: Mapping[Scope, int],
    scope_resolver: ScopeResolver | None,
) -> Task:
    call = dependency.call
    assert call is not None
    scope = dependency.scope

    if dependency.call in {d.call for d in path}:
        raise DependencyCycleError(
            "Dependencies are in a cycle",
            list(path.keys()),
        )

    params = get_params(dependency, binds, path)

    positional_parameters: list[Task] = []
    keyword_parameters: dict[str, Task] = {}
    subtasks: list[Task] = []
    dep_params: list[DependencyParameter] = []

    path[dependency] = None  # any value will do, we only use the keys

    for param in params:
        dep_params.append(param)
        if param.dependency.call is not None:
            child_task = build_task(
                param.dependency,
                binds,
                tasks,
                task_dag,
                dependent_dag,
                path,
                scope_idxs,
                scope_resolver,
            )
            subtasks.append(child_task)
            if param.parameter is not None:
                if param.parameter.kind in POSITIONAL_PARAMS:
                    positional_parameters.append(child_task)
                else:
                    keyword_parameters[param.parameter.name] = child_task
        if (
            param.dependency not in dependent_dag
            and param.dependency.cache_key not in tasks
        ):
            dependent_dag[param.dependency] = []
    if scope_resolver:
        child_scopes = [st.scope for st in subtasks]
        scope = scope_resolver(dependency, child_scopes, tuple(scope_idxs.keys()))

    if dependency.cache_key in tasks:
        if tasks[dependency.cache_key].scope != scope:
            raise SolvingError(
                f"{dependency.call} was used with multiple scopes",
                path=list(path.keys()),
            )
        path.pop(dependency)
        return tasks[dependency.cache_key]

    task: Task
    if is_async_gen_callable(call):
        if dependency.use_cache:
            task = CachedAsyncContextManagerTask(
                scope=scope,
                dependent=dependency,
                call=call,  # type: ignore[arg-type]
                cache_key=dependency.cache_key,
                task_id=len(tasks),
                positional_parameters=positional_parameters,
                keyword_parameters=keyword_parameters,
            )
        else:
            task = NotCachedAsyncContextManagerTask(
                scope=scope,
                call=call,  # type: ignore[arg-type]
                dependent=dependency,
                task_id=len(tasks),
                positional_parameters=positional_parameters,
                keyword_parameters=keyword_parameters,
            )
    elif is_gen_callable(call):
        if dependency.use_cache:
            task = CachedSyncContextManagerTask(
                scope=scope,
                call=call,  # type: ignore[arg-type]
                dependent=dependency,
                cache_key=dependency.cache_key,
                task_id=len(tasks),
                positional_parameters=positional_parameters,
                keyword_parameters=keyword_parameters,
            )
        else:
            task = NotCachedSyncContextManagerTask(
                scope=scope,
                call=call,  # type: ignore[arg-type]
                dependent=dependency,
                task_id=len(tasks),
                positional_parameters=positional_parameters,
                keyword_parameters=keyword_parameters,
            )
    elif is_coroutine_callable(call):
        if dependency.use_cache:
            task = CachedAsyncTask(
                scope=scope,
                call=call,  # type: ignore[arg-type]
                dependent=dependency,
                cache_key=dependency.cache_key,
                task_id=len(tasks),
                positional_parameters=positional_parameters,
                keyword_parameters=keyword_parameters,
            )
        else:
            task = NotCachedAsyncTask(
                scope=scope,
                call=call,  # type: ignore[arg-type]
                dependent=dependency,
                task_id=len(tasks),
                positional_parameters=positional_parameters,
                keyword_parameters=keyword_parameters,
            )
    else:
        if dependency.use_cache:
            task = CachedSyncTask(
                scope=scope,
                call=call,
                dependent=dependency,
                cache_key=dependency.cache_key,
                task_id=len(tasks),
                positional_parameters=positional_parameters,
                keyword_parameters=keyword_parameters,
            )
        else:
            task = NotCachedSyncTask(
                scope=scope,
                call=call,
                dependent=dependency,
                task_id=len(tasks),
                positional_parameters=positional_parameters,
                keyword_parameters=keyword_parameters,
            )

    dependent_dag[dependency] = dep_params
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
    dependency: DependentBase[T],
    scopes: Sequence[Scope],
    binds: Iterable[BindHook],
    scope_resolver: ScopeResolver | None,
) -> SolvedDependent[T]:
    """Solve a dependency.

    Returns a SolvedDependent that can be executed to get the dependency's value.
    """
    # If the dependency itself is a bind, replace it
    for hook in binds:
        match = hook(None, dependency)
        if match:
            dependency = match

    if dependency.call is None:  # pragma: no cover
        raise ValueError("DependentBase.call must not be None")

    task_dag: dict[Task, list[Task]] = {}
    dep_dag: dict[DependentBase[Any], list[DependencyParameter]] = {}
    scope_idxs = {scope: idx for idx, scope in enumerate(scopes)}

    # this is implemented recursively
    # which will crash on DAGs with depth > 1000 (default recursion limit)
    # if we encounter that in a real world use case
    # we can just rewrite this to be iterative
    root_task = build_task(
        dependency=dependency,
        binds=binds,
        tasks={},
        task_dag=task_dag,
        dependent_dag=dep_dag,
        # we use a dict to represent the path so that we can have
        # both O(1) lookups, and an ordered mutable sequence (via dict keys)
        # we simply ignore / don't use the dict values
        path={},
        scope_idxs=scope_idxs,
        scope_resolver=scope_resolver,
    )

    ts = TopologicalSorter(task_dag)
    static_order = tuple(ts.copy().static_order())
    ts.prepare()
    assert dependency.call is not None
    solved = SolvedDependent(
        dependency=dependency,
        dag=dep_dag,
        root_task=root_task,
        topological_sorter=ts,
        static_order=static_order,
        empty_results=[None] * len(task_dag),
    )
    return solved


Dependency = Any

DependencyType = TypeVar("DependencyType")


class SolvedDependent(Generic[DependencyType]):
    """Representation of a fully solved dependency as DAG.

    A SolvedDependent could be a user's endpoint/controller function.
    """

    dependency: DependentBase[DependencyType]
    dag: Mapping[DependentBase[Any], Iterable[DependencyParameter]]
    # container_cache can be used by the creating container to store data that is tied
    # to the SolvedDependent
    container_cache: typing.Any

    def __init__(
        self,
        dependency: DependentBase[DependencyType],
        dag: Mapping[DependentBase[Any], Iterable[DependencyParameter]],
        root_task: Task,
        topological_sorter: TopologicalSorter[Task],
        static_order: Iterable[Task],
        empty_results: list[Any],
    ):
        self.dependency = dependency
        self.dag = dag
        self._root_task = root_task
        self._topological_sorter = topological_sorter
        self._static_order = static_order
        self._empty_results = empty_results

    def _prepare_execution(
        self,
        stacks: Mapping[Scope, AsyncExitStack | ExitStack],
        cache: ScopeMap[CacheKey, Any],
        values: Mapping[DependencyProvider, Any] | None = None,
    ) -> tuple[list[Any], SupportsTaskGraph, ExecutionState, Task,]:
        results = self._empty_results.copy()
        if values is None:
            values = EMPTY_VALUES
        execution_state = ExecutionState(
            values=values,
            stacks=stacks,
            results=results,
            cache=cache,
        )
        ts = TaskGraph(
            self._topological_sorter,
            self._static_order,
        )
        return (
            results,
            ts,
            execution_state,
            self._root_task,
        )

    def execute_sync(
        self,
        executor: SupportsSyncExecutor,
        state: ScopeState,
        values: Mapping[DependencyProvider, Any] | None = None,
    ) -> DependencyType:
        """Execute an already solved dependency.

        This method is synchronous and uses a synchronous executor,
        but the executor may still be able to execute async dependencies.
        """
        results, ts, execution_state, root_task = self._prepare_execution(
            stacks=state.stacks,
            cache=state.cached_values,
            values=values,
        )
        executor.execute_sync(ts, execution_state)
        return results[root_task.task_id]  # type: ignore[no-any-return]

    async def execute_async(
        self,
        executor: SupportsAsyncExecutor,
        state: ScopeState,
        values: Mapping[DependencyProvider, Any] | None = None,
    ) -> DependencyType:
        """Execute an already solved dependency."""
        results, ts, execution_state, root_task = self._prepare_execution(
            stacks=state.stacks,
            cache=state.cached_values,
            values=values,
        )
        await executor.execute_async(ts, execution_state)
        return results[root_task.task_id]  # type: ignore[no-any-return]


class Container:
    """Solve and execute dependencies.

    Generally you will want one Container per application.
    There is not performance advantage to re-using a container, the only reason to do so is to share binds.
    For each "thing" you want to wire with di and execute you'll want to call `Container.solve()`
    exactly once and then keep a reference to the returned `SolvedDependent` to pass to `Container.execute`.
    Solving is very expensive so avoid doing it in a hot loop.
    """

    __slots__ = ("_bind_hooks",)

    _bind_hooks: list[BindHook]

    def __init__(self) -> None:
        self._bind_hooks = []

    def bind(
        self,
        hook: BindHook,
    ) -> ContextManager[None]:
        """Replace a dependency provider with a new one.

        This can be used as a function (for a permanent bind, cleared when `scope` is exited)
        or as a context manager (the bind will be cleared when the context manager exits).
        """

        self._bind_hooks.append(hook)

        @contextmanager
        def unbind() -> Generator[None, None, None]:
            try:
                yield
            finally:
                self._bind_hooks.remove(hook)

        return unbind()

    def solve(
        self,
        dependency: DependentBase[DependencyType],
        scopes: Sequence[Scope],
        scope_resolver: ScopeResolver | None = None,
    ) -> SolvedDependent[DependencyType]:
        """Build the dependency graph.

        Should happen once, maybe during startup.

        Solving dependencies can be slow.
        """
        return solve(dependency, scopes, self._bind_hooks, scope_resolver)

    def enter_scope(
        self, scope: Scope, state: ScopeState | None = None
    ) -> FusedContextManager[ScopeState]:
        state = state or ScopeState()
        return state.enter_scope(scope)

    def execute_sync(
        self,
        solved: SolvedDependent[DependencyType],
        executor: SupportsSyncExecutor,
        *,
        state: ScopeState,
        values: Mapping[DependencyProvider, Any] | None = None,
    ) -> DependencyType:
        """Execute an already solved dependency.
        This method is synchronous and uses a synchronous executor,
        but the executor may still be able to execute async dependencies.
        """
        warn(
            "Container.execute_sync is deprecated; use SolvedDependant.execute_async instead"
        )
        return solved.execute_sync(
            executor=executor,
            state=state,
            values=values,
        )

    async def execute_async(
        self,
        solved: SolvedDependent[DependencyType],
        executor: SupportsAsyncExecutor,
        *,
        state: ScopeState,
        values: Mapping[DependencyProvider, Any] | None = None,
    ) -> DependencyType:
        """Execute an already solved dependency."""
        warn(
            "Container.execute_async is deprecated; use SolvedDependant.execute_async instead"
        )
        return await solved.execute_async(
            executor=executor,
            state=state,
            values=values,
        )
