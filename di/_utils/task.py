from __future__ import annotations

import contextlib
from contextlib import AsyncExitStack, ExitStack
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    NamedTuple,
    Tuple,
    TypeVar,
    Union,
)

from di._utils.inspect import (
    is_async_gen_callable,
    is_coroutine_callable,
    is_gen_callable,
)
from di._utils.scope_map import ScopeMap
from di._utils.types import CacheKey
from di.api.dependencies import DependantBase
from di.api.providers import DependencyProvider
from di.api.scopes import Scope
from di.exceptions import IncompatibleDependencyError


class ExecutionState(NamedTuple):
    stacks: Mapping[Scope, Union[AsyncExitStack, ExitStack]]
    results: List[Any]
    cache: ScopeMap[CacheKey, Any]
    values: Mapping[DependencyProvider, Any]


DependencyType = TypeVar("DependencyType")


UNSET: Any = object()


class Task:
    __slots__ = (
        "wrapped_call",
        "user_function",
        "scope",
        "cache_key",
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
        cache_key: CacheKey,
        dependant: DependantBase[Any],
        task_id: int,
        positional_parameters: Iterable[Task],
        keyword_parameters: Iterable[Tuple[str, Task]],
    ) -> None:
        self.scope = scope
        self.user_function = call
        self.cache_key = cache_key
        self.dependant = dependant
        self.task_id = task_id
        if is_async_gen_callable(self.user_function):
            self.wrapped_call = contextlib.asynccontextmanager(call)  # type: ignore[arg-type]
            if use_cache:
                self.compute = self.compute_async_cm_cache
            else:
                self.compute = self.compute_async_cm_no_cache
        elif is_coroutine_callable(self.user_function):
            self.wrapped_call = self.user_function
            if use_cache:
                self.compute = self.compute_async_coro_cache
            else:
                self.compute = self.compute_async_coro_no_cache
        elif is_gen_callable(call):
            self.wrapped_call = contextlib.contextmanager(call)  # type: ignore[arg-type]
            if use_cache:
                self.compute = self.compute_sync_cm_cache
            else:
                self.compute = self.compute_sync_cm_no_cache
        else:
            self.wrapped_call = call
            if use_cache:
                self.compute = self.compute_sync_func_cache
            else:
                self.compute = self.compute_sync_func_no_cache

        self.call_user_func_with_deps = self.generate_execute_fn(
            self.wrapped_call, positional_parameters, keyword_parameters
        )

    def __hash__(self) -> int:
        return self.task_id

    def generate_execute_fn(
        self,
        call: DependencyProvider,
        positional_parameters: Iterable[Task],
        keyword_parameters: Iterable[Tuple[str, Task]],
    ) -> Callable[[List[Any]], Any]:
        # this codegen speeds up argument collection and passing
        # by avoiding creation of intermediary containers to store the values
        positional_arg_template = "results[{}]"
        keyword_arg_template = "{}=results[{}]"
        args: List[str] = []
        for task in positional_parameters:
            args.append(positional_arg_template.format(task.task_id))
        for keyword, task in keyword_parameters:
            args.append(keyword_arg_template.format(keyword, task.task_id))
        lcls: Dict[str, Any] = {}
        glbls = {"call": call}
        exec(f'def execute(results): return call({",".join(args)})', glbls, lcls)
        return lcls["execute"]  # type: ignore[no-any-return]

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(scope={self.scope}, call={self.user_function})"
        )

    async def compute_async_coro_cache(self, state: ExecutionState) -> None:
        if self.user_function in state.values:
            state.results[self.task_id] = state.values[self.user_function]
            return
        value = state.cache.get_key(self.cache_key, scope=self.scope, default=UNSET)
        if value is not UNSET:
            state.results[self.task_id] = value
            return
        dependency_value = await self.call_user_func_with_deps(state.results)
        state.results[self.task_id] = dependency_value
        state.cache.set(self.cache_key, dependency_value, scope=self.scope)

    async def compute_async_coro_no_cache(self, state: ExecutionState) -> None:
        if self.user_function in state.values:
            state.results[self.task_id] = state.values[self.user_function]
            return
        dependency_value = await self.call_user_func_with_deps(state.results)
        state.results[self.task_id] = dependency_value

    async def compute_async_cm_cache(self, state: ExecutionState) -> None:
        if self.user_function in state.values:
            state.results[self.task_id] = state.values[self.user_function]
            return
        value = state.cache.get_key(self.cache_key, scope=self.scope, default=UNSET)
        if value is not UNSET:
            state.results[self.task_id] = value
            return
        try:
            enter = state.stacks[self.scope].enter_async_context  # type: ignore[union-attr]
        except AttributeError:
            raise IncompatibleDependencyError(
                f"The dependency {self.user_function} is an awaitable dependency"
                f" and canot be used in the sync scope {self.scope}"
            ) from None

        dependency_value: Any = await enter(
            self.call_user_func_with_deps(state.results)
        )
        state.results[self.task_id] = dependency_value
        state.cache.set(self.cache_key, dependency_value, scope=self.scope)

    async def compute_async_cm_no_cache(self, state: ExecutionState) -> None:
        if self.user_function in state.values:
            state.results[self.task_id] = state.values[self.user_function]
            return
        try:
            enter = state.stacks[self.scope].enter_async_context  # type: ignore[union-attr]
        except AttributeError:
            raise IncompatibleDependencyError(
                f"The dependency {self.user_function} is an awaitable dependency"
                f" and canot be used in the sync scope {self.scope}"
            ) from None
        dependency_value: Any = await enter(
            self.call_user_func_with_deps(state.results)
        )
        state.results[self.task_id] = dependency_value

    def compute_sync_cm_cache(self, state: ExecutionState) -> None:
        if self.user_function in state.values:
            state.results[self.task_id] = state.values[self.user_function]
            return
        value = state.cache.get_key(self.cache_key, scope=self.scope, default=UNSET)
        if value is not UNSET:
            state.results[self.task_id] = value
            return
        val = state.stacks[self.scope].enter_context(
            self.call_user_func_with_deps(state.results)
        )
        state.results[self.task_id] = val
        state.cache.set(self.cache_key, val, scope=self.scope)

    def compute_sync_cm_no_cache(self, state: ExecutionState) -> None:
        if self.user_function in state.values:
            state.results[self.task_id] = state.values[self.user_function]
            return
        state.results[self.task_id] = state.stacks[self.scope].enter_context(
            self.call_user_func_with_deps(state.results)
        )

    def compute_sync_func_cache(self, state: ExecutionState) -> None:
        if self.user_function in state.values:
            state.results[self.task_id] = state.values[self.user_function]
            return
        value = state.cache.get_key(self.cache_key, scope=self.scope, default=UNSET)
        if value is not UNSET:
            state.results[self.task_id] = value
            return
        val = self.call_user_func_with_deps(state.results)
        state.results[self.task_id] = val
        state.cache.set(self.cache_key, val, scope=self.scope)

    def compute_sync_func_no_cache(self, state: ExecutionState) -> None:
        if self.user_function in state.values:
            state.results[self.task_id] = state.values[self.user_function]
            return

        state.results[self.task_id] = self.call_user_func_with_deps(state.results)
