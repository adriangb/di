from __future__ import annotations

import contextlib
from contextlib import AsyncExitStack, ExitStack
from typing import (
    Any,
    AsyncContextManager,
    Awaitable,
    Callable,
    ContextManager,
    Generic,
    Iterable,
    Mapping,
    TypeVar,
    Union,
)

from di._utils.scope_map import ScopeMap
from di._utils.types import CacheKey
from di.api.dependencies import DependentBase
from di.api.providers import (
    AsyncGeneratorProvider,
    CallableProvider,
    CoroutineProvider,
    DependencyProvider,
    GeneratorProvider,
)
from di.api.scopes import Scope
from di.exceptions import IncompatibleDependencyError


class ExecutionState:
    __slots__ = (
        "_stacks",
        "_results",
        "_cache",
        "_values",
    )

    def __init__(
        self,
        stacks: Mapping[Scope, AsyncExitStack | ExitStack],
        results: list[Any],
        cache: ScopeMap[CacheKey, Any],
        values: Mapping[DependencyProvider, Any],
    ) -> None:
        self._stacks = stacks
        self._results = results
        self._cache = cache
        self._values = values


DependencyType = TypeVar("DependencyType")


UNSET: Any = object()


def generate_call_with_deps_from_results(
    call: _ExecutableCallable,
    positional_parameters: PositionalTaskParameters,
    keyword_parameters: KeywordTaskParameters,
) -> Callable[[list[Any]], Any]:
    # this codegen speeds up argument collection and passing
    # by avoiding creation of intermediary containers to store the values
    positional_arg_template = "results[{}]"
    keyword_arg_template = "{}=results[{}]"
    args: list[str] = []
    for task in positional_parameters:
        args.append(positional_arg_template.format(task.task_id))
    for keyword, task in keyword_parameters.items():
        args.append(keyword_arg_template.format(keyword, task.task_id))
    locals: dict[str, Any] = {}
    globals = {"call": call}
    exec(f'def execute(results): return call({",".join(args)})', globals, locals)
    return locals["execute"]  # type: ignore[no-any-return]


ProviderType = TypeVar(
    "ProviderType", bound=Union[CallableProvider[Any], CoroutineProvider[Any]]
)


_ExecutableCallable = Union[
    Callable[..., Any],
    Callable[..., Awaitable[Any]],
    Callable[..., ContextManager[Any]],
    Callable[..., AsyncContextManager[Any]],
]


class AsyncTask:
    __slots__ = ()

    dependant: DependentBase[Any]

    async def compute(self, state: ExecutionState) -> None:
        ...


class SyncTask:
    __slots__ = ()

    dependant: DependentBase[Any]

    def compute(self, state: ExecutionState) -> None:
        ...


class _TaskBase(Generic[ProviderType]):
    __slots__ = (
        "scope",
        "dependent",
        "unwrapped_call",
        "task_id",
        "call_user_func_with_deps",
    )

    def __init__(
        self,
        scope: Scope,
        dependent: DependentBase[Any],
        call: ProviderType,
        task_id: int,
        positional_parameters: PositionalTaskParameters,
        keyword_parameters: KeywordTaskParameters,
    ) -> None:
        self.dependent = dependent
        self.scope = scope
        assert dependent.call is not None
        self.unwrapped_call = dependent.call
        self.task_id = task_id
        self.call_user_func_with_deps = generate_call_with_deps_from_results(
            self.transform_call(call), positional_parameters, keyword_parameters
        )

    def __hash__(self) -> int:
        return self.task_id

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(scope={self.scope}, call={self.unwrapped_call})"
        )

    def transform_call(self, call: ProviderType) -> _ExecutableCallable:
        return call


PositionalTaskParameters = Iterable[_TaskBase[Any]]
KeywordTaskParameters = Mapping[str, _TaskBase[Any]]


class _CachedTaskBase(_TaskBase[ProviderType]):
    __slots__ = ("cache_key",)

    def __init__(
        self,
        scope: Scope,
        dependent: DependentBase[Any],
        call: ProviderType,
        cache_key: CacheKey,
        task_id: int,
        positional_parameters: PositionalTaskParameters,
        keyword_parameters: KeywordTaskParameters,
    ) -> None:
        super().__init__(
            dependent=dependent,
            scope=scope,
            call=call,
            task_id=task_id,
            positional_parameters=positional_parameters,
            keyword_parameters=keyword_parameters,
        )
        self.cache_key = cache_key


class _TransformSyncCM:
    __slots__ = ()

    def transform_call(self, call: GeneratorProvider[Any]) -> _ExecutableCallable:
        return contextlib.contextmanager(call)


class _TransformAsyncCM:
    __slots__ = ()

    def transform_call(self, call: AsyncGeneratorProvider[Any]) -> _ExecutableCallable:
        return contextlib.asynccontextmanager(call)


class NotCachedSyncTask(_TaskBase[CallableProvider[Any]], SyncTask):
    def compute(self, state: ExecutionState) -> None:
        if self.unwrapped_call in state._values:
            state._results[self.task_id] = state._values[self.unwrapped_call]
            return
        val = self.call_user_func_with_deps(state._results)
        state._results[self.task_id] = val


class CachedSyncTask(_CachedTaskBase[CallableProvider[Any]], SyncTask):
    def compute(self, state: ExecutionState) -> None:
        if self.unwrapped_call in state._values:
            state._results[self.task_id] = state._values[self.unwrapped_call]
            return
        value = state._cache.get_key(self.cache_key, scope=self.scope, default=UNSET)
        if value is not UNSET:
            state._results[self.task_id] = value
            return
        val = self.call_user_func_with_deps(state._results)
        state._results[self.task_id] = val
        state._cache.set(self.cache_key, val, scope=self.scope)


class NotCachedSyncContextManagerTask(
    _TransformSyncCM, _TaskBase[GeneratorProvider[Any]], SyncTask
):
    def compute(self, state: ExecutionState) -> None:
        if self.unwrapped_call in state._values:
            state._results[self.task_id] = state._values[self.unwrapped_call]
            return
        val = state._stacks[self.scope].enter_context(
            self.call_user_func_with_deps(state._results)
        )
        state._results[self.task_id] = val


class CachedSyncContextManagerTask(
    _TransformSyncCM, _CachedTaskBase[GeneratorProvider[Any]], SyncTask
):
    def compute(self, state: ExecutionState) -> None:
        if self.unwrapped_call in state._values:
            state._results[self.task_id] = state._values[self.unwrapped_call]
            return
        value = state._cache.get_key(self.cache_key, scope=self.scope, default=UNSET)
        if value is not UNSET:
            state._results[self.task_id] = value
            return
        val = state._stacks[self.scope].enter_context(
            self.call_user_func_with_deps(state._results)
        )
        state._results[self.task_id] = val
        state._cache.set(self.cache_key, val, scope=self.scope)


class NotCachedAsyncTask(_TaskBase[CoroutineProvider[Any]], AsyncTask):
    async def compute(self, state: ExecutionState) -> None:
        if self.unwrapped_call in state._values:
            state._results[self.task_id] = state._values[self.unwrapped_call]
            return
        val = await self.call_user_func_with_deps(state._results)
        state._results[self.task_id] = val


class CachedAsyncTask(_CachedTaskBase[CoroutineProvider[Any]], AsyncTask):
    async def compute(self, state: ExecutionState) -> None:
        if self.unwrapped_call in state._values:
            state._results[self.task_id] = state._values[self.unwrapped_call]
            return
        value = state._cache.get_key(self.cache_key, scope=self.scope, default=UNSET)
        if value is not UNSET:
            state._results[self.task_id] = value
            return
        val = await self.call_user_func_with_deps(state._results)
        state._results[self.task_id] = val
        state._cache.set(self.cache_key, val, scope=self.scope)


class NotCachedAsyncContextManagerTask(
    _TransformAsyncCM, _TaskBase[AsyncGeneratorProvider[Any]], AsyncTask
):
    async def compute(self, state: ExecutionState) -> None:
        if self.unwrapped_call in state._values:
            state._results[self.task_id] = state._values[self.unwrapped_call]
            return
        try:
            val = await state._stacks[self.scope].enter_async_context(  # type: ignore[union-attr]
                self.call_user_func_with_deps(state._results)
            )
        except AttributeError:
            raise IncompatibleDependencyError(
                f"The dependency {self.unwrapped_call} is an awaitable dependency"
                f" and cannot be used in the sync scope {self.scope}"
            ) from None
        state._results[self.task_id] = val


class CachedAsyncContextManagerTask(
    _TransformAsyncCM, _CachedTaskBase[AsyncGeneratorProvider[Any]], AsyncTask
):
    async def compute(self, state: ExecutionState) -> None:
        if self.unwrapped_call in state._values:
            state._results[self.task_id] = state._values[self.unwrapped_call]
            return
        value = state._cache.get_key(self.cache_key, scope=self.scope, default=UNSET)
        if value is not UNSET:
            state._results[self.task_id] = value
            return
        try:
            val = await state._stacks[self.scope].enter_async_context(  # type: ignore[union-attr]
                self.call_user_func_with_deps(state._results)
            )
        except AttributeError:
            raise IncompatibleDependencyError(
                f"The dependency {self.unwrapped_call} is an awaitable dependency"
                f" and cannot be used in the sync scope {self.scope}"
            ) from None
        state._results[self.task_id] = val
        state._cache.set(self.cache_key, val, scope=self.scope)


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
