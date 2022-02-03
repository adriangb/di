from __future__ import annotations

import contextlib
from contextlib import AsyncExitStack, ExitStack
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

from di._utils.inspect import (
    is_async_gen_callable,
    is_coroutine_callable,
    is_gen_callable,
)
from di._utils.scope_map import ScopeMap
from di.api.dependencies import DependantBase
from di.api.executor import State as ExecutorState
from di.api.executor import Task as ExecutorTask
from di.api.providers import DependencyProvider
from di.api.scopes import Scope
from di.exceptions import IncompatibleDependencyError


class ExecutionState(ExecutorState):
    __slots__ = (
        "stacks",
        "results",
        "values",
        "toplogical_sorter",
        "cache",
    )

    def __init__(
        self,
        stacks: Mapping[Scope, Union[AsyncExitStack, ExitStack]],
        results: Dict[int, Any],
        toplogical_sorter: TopologicalSorter[Task],
        cache: ScopeMap[DependencyProvider, Any],
        values: Mapping[DependencyProvider, Any],
    ):
        self.stacks = stacks
        self.results = results
        self.toplogical_sorter = toplogical_sorter
        self.cache = cache
        self.values = values


DependencyType = TypeVar("DependencyType")


def gather_new_tasks(
    state: ExecutionState,
) -> Generator[Optional[ExecutorTask], None, None]:
    """Look amongst our dependant tasks to see if any of them are now dependency free"""
    ready = state.toplogical_sorter.get_ready()
    if not ready and not state.toplogical_sorter.is_active():
        yield None
        return
    yield from ready


UNSET: Any = object()


class Task:
    __slots__ = (
        "wrapped_call",
        "user_function",
        "scope",
        "is_async",
        "dependant",
        "task_id",
        "call_user_func_with_deps",
        "compute",
    )

    compute: Any
    wrapped_call: DependencyProvider
    user_function: DependencyProvider

    def __init__(
        self,
        scope: Scope,
        call: DependencyProvider,
        use_cache: bool,
        dependant: DependantBase[Any],
        task_id: int,
        positional_parameters: Iterable[Task],
        keyword_parameters: Iterable[Tuple[str, Task]],
    ) -> None:
        self.scope = scope
        self.user_function = call
        self.dependant = dependant
        self.task_id = task_id
        if is_async_gen_callable(self.user_function):
            self.is_async = True
            self.wrapped_call = contextlib.asynccontextmanager(call)  # type: ignore[arg-type]
            if use_cache:
                self.compute = self.compute_async_cm_cache
            else:
                self.compute = self.compute_async_cm_no_cache
        elif is_coroutine_callable(self.user_function):
            self.is_async = True
            self.wrapped_call = self.user_function
            if use_cache:
                self.compute = self.compute_async_coro_cache
            else:
                self.compute = self.compute_async_coro_no_cache
        elif is_gen_callable(call):
            self.is_async = False
            self.wrapped_call = contextlib.contextmanager(call)  # type: ignore[arg-type]
            if use_cache:
                self.compute = self.compute_sync_cm_cache
            else:
                self.compute = self.compute_sync_cm_no_cache
        else:
            self.is_async = False
            self.wrapped_call = call
            if use_cache:
                self.compute = self.compute_sync_func_cache
            else:
                self.compute = self.compute_sync_func_no_cache

        self.call_user_func_with_deps = self.generate_execute_fn(
            positional_parameters, keyword_parameters
        )

    def generate_execute_fn(
        self,
        positional_parameters: Iterable[Task],
        keyword_parameters: Iterable[Tuple[str, Task]],
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
        return (
            f"{self.__class__.__name__}(scope={self.scope}, call={self.user_function})"
        )

    async def compute_async_coro_cache(
        self, state: ExecutionState
    ) -> Iterable[Union[None, ExecutorTask]]:
        if self.user_function in state.values:
            state.results[self.task_id] = state.values[self.user_function]
            state.toplogical_sorter.done(self)
            return gather_new_tasks(state)

        value = state.cache.get_from_scope(
            self.user_function, scope=self.scope, default=UNSET
        )
        if value is not UNSET:
            state.results[self.task_id] = value
            state.toplogical_sorter.done(self)
            return gather_new_tasks(state)

        dependency_value = await self.call_user_func_with_deps(
            self.wrapped_call, state.results
        )

        state.results[self.task_id] = dependency_value
        state.toplogical_sorter.done(self)
        state.cache.set(self.user_function, dependency_value, scope=self.scope)
        return gather_new_tasks(state)

    async def compute_async_coro_no_cache(
        self, state: ExecutionState
    ) -> Iterable[Union[None, ExecutorTask]]:
        if self.user_function in state.values:
            state.results[self.task_id] = state.values[self.user_function]
            state.toplogical_sorter.done(self)
            return gather_new_tasks(state)

        dependency_value = await self.call_user_func_with_deps(
            self.wrapped_call, state.results
        )

        state.results[self.task_id] = dependency_value
        state.toplogical_sorter.done(self)
        return gather_new_tasks(state)  # type: ignore[arg-type,return-value]

    async def compute_async_cm_cache(
        self, state: ExecutionState
    ) -> Iterable[Union[None, ExecutorTask]]:
        if self.user_function in state.values:
            state.results[self.task_id] = state.values[self.user_function]
            state.toplogical_sorter.done(self)
            return gather_new_tasks(state)

        value = state.cache.get_from_scope(
            self.wrapped_call, scope=self.scope, default=UNSET
        )
        if value is not UNSET:
            state.results[self.task_id] = value
            state.toplogical_sorter.done(self)
            return gather_new_tasks(state)

        try:
            enter = state.stacks[self.scope].enter_async_context  # type: ignore[union-attr]
        except AttributeError:
            raise IncompatibleDependencyError(
                f"The dependency {self.user_function} is an awaitable dependency"
                f" and canot be used in the sync scope {self.scope}"
            ) from None

        dependency_value: Any = await enter(
            self.call_user_func_with_deps(self.wrapped_call, state.results)
        )

        state.results[self.task_id] = dependency_value
        state.toplogical_sorter.done(self)
        state.cache.set(self.user_function, dependency_value, scope=self.scope)
        return gather_new_tasks(state)  # type: ignore[arg-type,return-value]

    async def compute_async_cm_no_cache(
        self, state: ExecutionState
    ) -> Iterable[Union[None, ExecutorTask]]:
        if self.user_function in state.values:
            state.results[self.task_id] = state.values[self.user_function]
            state.toplogical_sorter.done(self)
            return gather_new_tasks(state)

        try:
            enter = state.stacks[self.scope].enter_async_context  # type: ignore[union-attr]
        except AttributeError:
            raise IncompatibleDependencyError(
                f"The dependency {self.user_function} is an awaitable dependency"
                f" and canot be used in the sync scope {self.scope}"
            ) from None

        dependency_value: Any = await enter(
            self.call_user_func_with_deps(self.wrapped_call, state.results)
        )

        state.results[self.task_id] = dependency_value
        state.toplogical_sorter.done(self)
        return gather_new_tasks(state)

    def compute_sync_cm_cache(
        self, state: ExecutionState
    ) -> Iterable[Union[None, ExecutorTask]]:
        if self.user_function in state.values:
            state.results[self.task_id] = state.values[self.user_function]
            state.toplogical_sorter.done(self)
            return gather_new_tasks(state)

        value = state.cache.get_from_scope(
            self.user_function, scope=self.scope, default=UNSET
        )
        if value is not UNSET:
            state.results[self.task_id] = value
            state.toplogical_sorter.done(self)
            return gather_new_tasks(state)

        val = state.stacks[self.scope].enter_context(
            self.call_user_func_with_deps(self.wrapped_call, state.results)
        )
        state.results[self.task_id] = val
        state.toplogical_sorter.done(self)
        state.cache.set(self.user_function, val, scope=self.scope)
        return gather_new_tasks(state)

    def compute_sync_cm_no_cache(
        self, state: ExecutionState
    ) -> Iterable[Union[None, ExecutorTask]]:
        if self.user_function in state.values:
            state.results[self.task_id] = state.values[self.user_function]
            state.toplogical_sorter.done(self)
            return gather_new_tasks(state)

        state.results[self.task_id] = state.stacks[self.scope].enter_context(
            self.call_user_func_with_deps(self.wrapped_call, state.results)
        )
        state.toplogical_sorter.done(self)
        return gather_new_tasks(state)

    def compute_sync_func_cache(
        self, state: ExecutionState
    ) -> Iterable[Union[None, ExecutorTask]]:
        if self.user_function in state.values:
            state.results[self.task_id] = state.values[self.user_function]
            state.toplogical_sorter.done(self)
            return gather_new_tasks(state)

        value = state.cache.get_from_scope(
            self.wrapped_call, scope=self.scope, default=UNSET
        )
        if value is not UNSET:
            state.results[self.task_id] = value
            state.toplogical_sorter.done(self)
            return gather_new_tasks(state)

        val = self.call_user_func_with_deps(self.wrapped_call, state.results)
        state.results[self.task_id] = val
        state.toplogical_sorter.done(self)
        state.cache.set(self.user_function, val, scope=self.scope)
        return gather_new_tasks(state)

    def compute_sync_func_no_cache(
        self, state: ExecutionState
    ) -> Iterable[Union[None, ExecutorTask]]:
        if self.user_function in state.values:
            state.results[self.task_id] = state.values[self.user_function]
            state.toplogical_sorter.done(self)
            return gather_new_tasks(state)

        state.results[self.task_id] = self.call_user_func_with_deps(
            self.wrapped_call, state.results
        )
        state.toplogical_sorter.done(self)
        return gather_new_tasks(state)
