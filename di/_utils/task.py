from __future__ import annotations

from contextlib import AsyncExitStack, ExitStack, asynccontextmanager, contextmanager
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Iterable,
    List,
    Mapping,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

from graphlib2 import TopologicalSorter

from di._utils.inspect import is_async_gen_callable, is_gen_callable
from di._utils.scope_map import ScopeMap
from di.api.dependencies import DependantBase
from di.api.executor import AsyncTask as ExecutorAsyncTask
from di.api.executor import SyncTask as ExecutorSyncTask
from di.api.executor import Task as ExecutorTask
from di.api.providers import DependencyProvider
from di.api.scopes import Scope
from di.exceptions import IncompatibleDependencyError


class ExecutionState:
    __slots__ = (
        "stacks",
        "results",
        "toplogical_sorter",
        "cache",
    )

    def __init__(
        self,
        stacks: Mapping[Scope, Union[AsyncExitStack, ExitStack]],
        results: Dict[int, Any],
        toplogical_sorter: TopologicalSorter[Union[AsyncTask, SyncTask]],
        cache: ScopeMap[DependencyProvider, Any],
    ):
        self.stacks = stacks
        self.results = results
        self.toplogical_sorter = toplogical_sorter
        self.cache = cache


DependencyType = TypeVar("DependencyType")


def gather_new_tasks(
    state: ExecutionState,
) -> Generator[Optional[ExecutorTask], None, None]:
    """Look amongst our dependant tasks to see if any of them are now dependency free"""
    res = state.results
    ts = state.toplogical_sorter
    while True:
        if not ts.is_active():
            yield None
            return
        ready = ts.get_ready()
        if not ready:
            break
        marked = False
        for t in ready:
            if t.task_id in res:
                # task was passed in by value or cached
                ts.done(t)
                marked = True
            else:
                yield t
        if not marked:
            # we didn't mark any nodes as done
            # so there's no point in calling get_ready() again
            break
    if not ts.is_active():
        yield None


UNSET: Any = object()


class Task:
    __slots__ = (
        "call",
        "scope",
        "use_cache",
        "dependant",
        "task_id",
        "call_user_func_with_deps",
    )

    def __init__(
        self,
        scope: Scope,
        call: DependencyProvider,
        use_cache: bool,
        dependant: DependantBase[Any],
        task_id: int,
        positional_parameters: Iterable[Union[AsyncTask, SyncTask]],
        keyword_parameters: Iterable[Tuple[str, Union[AsyncTask, SyncTask]]],
    ) -> None:
        self.use_cache = use_cache
        self.scope = scope
        self.call = call
        self.dependant = dependant
        self.task_id = task_id
        self.call_user_func_with_deps = self.generate_execute_fn(
            positional_parameters, keyword_parameters
        )

    def generate_execute_fn(
        self,
        positional_parameters: Iterable[Union[AsyncTask, SyncTask]],
        keyword_parameters: Iterable[Tuple[str, Union[AsyncTask, SyncTask]]],
    ) -> Callable[[Callable[..., Any], Dict[int, Any]], Any]:
        # this codegen speeds up argument collection and passing
        # by avoiding creation of intermediary containers to store the values
        positional_arg_template = "results[{}]"
        keyword_arg_template = "{}=results[{}]"
        args: List[str] = []
        for task in positional_parameters:
            args.append(positional_arg_template.format(task.task_id))
        for keyword, task in keyword_parameters:
            args.append(keyword_arg_template.format(keyword, task.task_id))
        out: Dict[str, Callable[..., Any]] = {}
        exec(f'def execute(call, results): return call({",".join(args)})', out)
        return out["execute"]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(scope={self.scope}, call={self.call})"


class AsyncTask(Task, ExecutorAsyncTask):
    __slots__ = ("is_generator",)

    def __init__(
        self,
        scope: Scope,
        call: DependencyProvider,
        use_cache: bool,
        dependant: DependantBase[Any],
        task_id: int,
        positional_parameters: Iterable[Union[AsyncTask, SyncTask]],
        keyword_parameters: Iterable[Tuple[str, Union[AsyncTask, SyncTask]]],
    ) -> None:
        super().__init__(
            scope,
            call,
            use_cache,
            dependant,
            task_id,
            positional_parameters,
            keyword_parameters,
        )
        self.is_generator = is_async_gen_callable(self.call)
        if self.is_generator:
            self.call = asynccontextmanager(self.call)  # type: ignore[arg-type]

    async def compute(  # type: ignore[override]  # we do it this way to avoid exposing implementation details to users
        self,
        state: ExecutionState,
    ) -> Iterable[Optional[ExecutorTask]]:
        if self.use_cache:
            value = state.cache.get_from_scope(
                self.call, scope=self.scope, default=UNSET
            )
            if value is not UNSET:
                state.results[self.task_id] = value
                state.toplogical_sorter.done(self)
                return gather_new_tasks(state)

        if self.is_generator:
            try:
                enter = state.stacks[self.scope].enter_async_context  # type: ignore[union-attr]
            except AttributeError:
                raise IncompatibleDependencyError(
                    f"The dependency {self.call} is an awaitable dependency"
                    f" and canot be used in the sync scope {self.scope}"
                ) from None
            state.results[self.task_id] = await enter(
                self.call_user_func_with_deps(self.call, state.results)
            )
        else:
            state.results[self.task_id] = await self.call_user_func_with_deps(
                self.call, state.results
            )

        state.toplogical_sorter.done(self)
        if self.use_cache:
            state.cache.set(self.call, state.results[self.task_id], scope=self.scope)
        return gather_new_tasks(state)


class SyncTask(Task, ExecutorSyncTask):
    __slots__ = ("is_generator",)

    def __init__(
        self,
        scope: Scope,
        call: DependencyProvider,
        use_cache: bool,
        dependant: DependantBase[Any],
        # task ID is just an arbitrary ID for each task
        # we could use id(instance) but having serial numbers
        # is a bit clear w.r.t. the intention
        task_id: int,
        positional_parameters: Iterable[Union[AsyncTask, SyncTask]],
        keyword_parameters: Iterable[Tuple[str, Union[AsyncTask, SyncTask]]],
    ) -> None:
        super().__init__(
            scope,
            call,
            use_cache,
            dependant,
            task_id,
            positional_parameters,
            keyword_parameters,
        )
        self.is_generator = is_gen_callable(self.call)
        if self.is_generator:
            self.call = contextmanager(self.call)  # type: ignore[arg-type]

    def compute(  # type: ignore[override]  # we do it this way to avoid exposing implementation details to users
        self,
        state: ExecutionState,
    ) -> Iterable[Optional[ExecutorTask]]:
        if self.use_cache:
            value = state.cache.get_from_scope(
                self.call, scope=self.scope, default=UNSET
            )
            if value is not UNSET:
                state.results[self.task_id] = value
                state.toplogical_sorter.done(self)
                return gather_new_tasks(state)

        if self.is_generator:
            state.results[self.task_id] = state.stacks[self.scope].enter_context(
                self.call_user_func_with_deps(self.call, state.results)
            )
        else:
            state.results[self.task_id] = self.call_user_func_with_deps(
                self.call, state.results
            )
        state.toplogical_sorter.done(self)
        if self.use_cache:
            state.cache.set(self.call, state.results[self.task_id], scope=self.scope)
        return gather_new_tasks(state)
