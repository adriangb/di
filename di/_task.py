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
    TypeVar,
    Union,
)

from di._utils.scope_map import ScopeMap
from di._utils.types import CacheKey
from di.api.providers import CallableProvider, DependencyProvider
from di.api.scopes import Scope
from di.exceptions import IncompatibleDependencyError


class ExecutionState(NamedTuple):
    stacks: Mapping[Scope, Union[AsyncExitStack, ExitStack]]
    results: List[Any]
    cache: ScopeMap[CacheKey, Any]
    values: Mapping[DependencyProvider, Any]


DependencyType = TypeVar("DependencyType")


UNSET: Any = object()


def generate_call_with_deps_from_results(
    call: DependencyProvider,
    positional_parameters: Iterable[_TaskBase],
    keyword_parameters: Mapping[str, _TaskBase],
) -> Callable[[List[Any]], Any]:
    # this codegen speeds up argument collection and passing
    # by avoiding creation of intermediary containers to store the values
    positional_arg_template = "results[{}]"
    keyword_arg_template = "{}=results[{}]"
    args: List[str] = []
    for task in positional_parameters:
        args.append(positional_arg_template.format(task.task_id))
    for keyword, task in keyword_parameters.items():
        args.append(keyword_arg_template.format(keyword, task.task_id))
    locals: Dict[str, Any] = {}
    globals = {"call": call}
    exec(f'def execute(results): return call({",".join(args)})', globals, locals)
    return locals["execute"]  # type: ignore[no-any-return]


class _TaskBase:
    def __init__(
        self,
        scope: Scope,
        call: DependencyProvider,
        unwrapped_call: Any,
        task_id: int,
        positional_parameters: Iterable[_TaskBase],
        keyword_parameters: Mapping[str, _TaskBase],
    ) -> None:
        self.scope = scope
        self.unwrapped_call = unwrapped_call
        self.task_id = task_id
        self.call_user_func_with_deps = generate_call_with_deps_from_results(
            call, positional_parameters, keyword_parameters
        )

    def __hash__(self) -> int:
        return self.task_id

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(scope={self.scope}, call={self.unwrapped_call})"
        )


class NotCachedSyncTask(_TaskBase):
    def __init__(
        self,
        scope: Scope,
        call: CallableProvider[Any],
        task_id: int,
        positional_parameters: Iterable[_TaskBase],
        keyword_parameters: Mapping[str, _TaskBase],
    ) -> None:
        super().__init__(
            scope=scope,
            call=call,
            unwrapped_call=call,
            task_id=task_id,
            positional_parameters=positional_parameters,
            keyword_parameters=keyword_parameters,
        )

    def compute(self, state: ExecutionState) -> None:
        if self.unwrapped_call in state.values:
            state.results[self.task_id] = state.values[self.unwrapped_call]
            return
        val = self.call_user_func_with_deps(state.results)
        state.results[self.task_id] = val


class CachedSyncTask(_TaskBase):
    def __init__(
        self,
        scope: Scope,
        call: CallableProvider[Any],
        cache_key: CacheKey,
        task_id: int,
        positional_parameters: Iterable[_TaskBase],
        keyword_parameters: Mapping[str, _TaskBase],
    ) -> None:
        super().__init__(
            scope=scope,
            call=call,
            unwrapped_call=call,
            task_id=task_id,
            positional_parameters=positional_parameters,
            keyword_parameters=keyword_parameters,
        )
        self.cache_key = cache_key

    def compute(self, state: ExecutionState) -> None:
        if self.unwrapped_call in state.values:
            state.results[self.task_id] = state.values[self.unwrapped_call]
            return
        value = state.cache.get_key(self.cache_key, scope=self.scope, default=UNSET)
        if value is not UNSET:
            state.results[self.task_id] = value
            return
        val = self.call_user_func_with_deps(state.results)
        state.results[self.task_id] = val
        state.cache.set(self.cache_key, val, scope=self.scope)


class NotCachedSyncContextManagerTask(_TaskBase):
    def __init__(
        self,
        scope: Scope,
        call: CallableProvider[Any],
        task_id: int,
        positional_parameters: Iterable[_TaskBase],
        keyword_parameters: Mapping[str, _TaskBase],
    ) -> None:
        super().__init__(
            scope=scope,
            call=contextlib.contextmanager(call),
            unwrapped_call=call,
            task_id=task_id,
            positional_parameters=positional_parameters,
            keyword_parameters=keyword_parameters,
        )

    def compute(self, state: ExecutionState) -> None:
        if self.unwrapped_call in state.values:
            state.results[self.task_id] = state.values[self.unwrapped_call]
            return
        val = state.stacks[self.scope].enter_context(
            self.call_user_func_with_deps(state.results)
        )
        state.results[self.task_id] = val


class CachedSyncContextManagerTask(_TaskBase):
    def __init__(
        self,
        scope: Scope,
        call: CallableProvider[Any],
        cache_key: CacheKey,
        task_id: int,
        positional_parameters: Iterable[_TaskBase],
        keyword_parameters: Mapping[str, _TaskBase],
    ) -> None:
        super().__init__(
            scope=scope,
            call=contextlib.contextmanager(call),
            unwrapped_call=call,
            task_id=task_id,
            positional_parameters=positional_parameters,
            keyword_parameters=keyword_parameters,
        )
        self.cache_key = cache_key

    def compute(self, state: ExecutionState) -> None:
        if self.unwrapped_call in state.values:
            state.results[self.task_id] = state.values[self.unwrapped_call]
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


class NotCachedAsyncTask(_TaskBase):
    def __init__(
        self,
        scope: Scope,
        call: CallableProvider[Any],
        task_id: int,
        positional_parameters: Iterable[_TaskBase],
        keyword_parameters: Mapping[str, _TaskBase],
    ) -> None:
        super().__init__(
            scope=scope,
            call=call,
            unwrapped_call=call,
            task_id=task_id,
            positional_parameters=positional_parameters,
            keyword_parameters=keyword_parameters,
        )

    async def compute(self, state: ExecutionState) -> None:
        if self.unwrapped_call in state.values:
            state.results[self.task_id] = state.values[self.unwrapped_call]
            return
        val = await self.call_user_func_with_deps(state.results)
        state.results[self.task_id] = val


class CachedAsyncTask(_TaskBase):
    def __init__(
        self,
        scope: Scope,
        call: CallableProvider[Any],
        cache_key: CacheKey,
        task_id: int,
        positional_parameters: Iterable[_TaskBase],
        keyword_parameters: Mapping[str, _TaskBase],
    ) -> None:
        super().__init__(
            scope=scope,
            call=call,
            unwrapped_call=call,
            task_id=task_id,
            positional_parameters=positional_parameters,
            keyword_parameters=keyword_parameters,
        )
        self.cache_key = cache_key

    async def compute(self, state: ExecutionState) -> None:
        if self.unwrapped_call in state.values:
            state.results[self.task_id] = state.values[self.unwrapped_call]
            return
        value = state.cache.get_key(self.cache_key, scope=self.scope, default=UNSET)
        if value is not UNSET:
            state.results[self.task_id] = value
            return
        val = await self.call_user_func_with_deps(state.results)
        state.results[self.task_id] = val
        state.cache.set(self.cache_key, val, scope=self.scope)


class NotCachedAsyncContextManagerTask(_TaskBase):
    def __init__(
        self,
        scope: Scope,
        call: CallableProvider[Any],
        task_id: int,
        positional_parameters: Iterable[_TaskBase],
        keyword_parameters: Mapping[str, _TaskBase],
    ) -> None:
        super().__init__(
            scope=scope,
            call=contextlib.asynccontextmanager(call),
            unwrapped_call=call,
            task_id=task_id,
            positional_parameters=positional_parameters,
            keyword_parameters=keyword_parameters,
        )

    async def compute(self, state: ExecutionState) -> None:
        if self.unwrapped_call in state.values:
            state.results[self.task_id] = state.values[self.unwrapped_call]
            return
        try:
            val = await state.stacks[self.scope].enter_async_context(  # type: ignore[union-attr]
                self.call_user_func_with_deps(state.results)
            )
        except AttributeError:
            raise IncompatibleDependencyError(
                f"The dependency {self.unwrapped_call} is an awaitable dependency"
                f" and cannot be used in the sync scope {self.scope}"
            ) from None
        state.results[self.task_id] = val


class CachedAsyncContextManagerTask(_TaskBase):
    def __init__(
        self,
        scope: Scope,
        call: CallableProvider[Any],
        cache_key: CacheKey,
        task_id: int,
        positional_parameters: Iterable[_TaskBase],
        keyword_parameters: Mapping[str, _TaskBase],
    ) -> None:
        super().__init__(
            scope=scope,
            call=contextlib.asynccontextmanager(call),
            unwrapped_call=call,
            task_id=task_id,
            positional_parameters=positional_parameters,
            keyword_parameters=keyword_parameters,
        )
        self.cache_key = cache_key

    async def compute(self, state: ExecutionState) -> None:
        if self.unwrapped_call in state.values:
            state.results[self.task_id] = state.values[self.unwrapped_call]
            return
        value = state.cache.get_key(self.cache_key, scope=self.scope, default=UNSET)
        if value is not UNSET:
            state.results[self.task_id] = value
            return
        try:
            val = await state.stacks[self.scope].enter_async_context(  # type: ignore[union-attr]
                self.call_user_func_with_deps(state.results)
            )
        except AttributeError:
            raise IncompatibleDependencyError(
                f"The dependency {self.unwrapped_call} is an awaitable dependency"
                f" and cannot be used in the sync scope {self.scope}"
            ) from None
        state.results[self.task_id] = val
        state.cache.set(self.cache_key, val, scope=self.scope)


Task = Union[
    CachedSyncContextManagerTask,
    CachedAsyncContextManagerTask,
    CachedAsyncTask,
    CachedSyncTask,
    NotCachedAsyncContextManagerTask,
    NotCachedAsyncTask,
    NotCachedSyncContextManagerTask,
    NotCachedSyncTask,
]
