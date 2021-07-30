from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncGenerator, Callable, Dict, Hashable, List, Tuple, overload

from anydep.concurrency import wrap_call
from anydep.exceptions import (
    DuplicatedDependencyError,
    DuplicateScopeError,
    UnknownScopeError,
)
from anydep.models import (
    AsyncGeneratorProvider,
    CallableProvider,
    CoroutineProvider,
    Dependant,
    Dependency,
    DependencyProvider,
    DependencyProviderType,
    DependencyType,
    GeneratorProvider,
    Scope,
)
from anydep.tasks import Task


class Container:
    def __init__(self) -> None:
        self._binds: Dict[DependencyProvider, Dependant[DependencyProvider]] = {}
        self._cached_values: Dict[Hashable, Dict[DependencyProvider, Dependency]] = {}
        self._stacks: Dict[Scope, AsyncExitStack] = {}
        self._scopes: List[Scope] = []
        self._infered_dependants: Dict[Tuple[DependencyProvider, str], Dependant[DependencyProvider]] = {}

    @overload
    def bind(
        self, target: AsyncGeneratorProvider[DependencyType], source: AsyncGeneratorProvider[DependencyType]
    ) -> None:
        ...

    @overload
    def bind(self, target: CoroutineProvider[DependencyType], source: CoroutineProvider[DependencyType]) -> None:
        ...

    @overload
    def bind(self, target: GeneratorProvider[DependencyType], source: GeneratorProvider[DependencyType]) -> None:
        ...

    @overload
    def bind(self, target: CallableProvider[DependencyType], source: CallableProvider[DependencyType]) -> None:
        ...

    def bind(self, target: DependencyProvider, source: DependencyProvider) -> None:
        self._binds[target] = Dependant(source)  # type: ignore
        for cached_values in self._cached_values.values():
            if target in cached_values:
                cached_values.pop(target)

    @asynccontextmanager
    async def enter_scope(self, scope: Scope) -> AsyncGenerator[None, None]:
        if scope in self._stacks:
            raise DuplicateScopeError(f"Scope {scope} has already been entered!")
        async with AsyncExitStack() as stack:
            self._scopes.append(scope)
            self._stacks[scope] = stack
            bound_providers = self._binds
            self._binds = bound_providers.copy()
            self._cached_values[scope] = {}
            try:
                yield
            finally:
                self._stacks.pop(scope)
                self._binds = bound_providers
                self._cached_values.pop(scope)
                self._scopes.pop()

    def _get_scope_index(self, scope: Scope) -> int:
        self._check_scope(scope)
        return self._scopes.index(scope)

    def _resolve_scope(self, dependant_scope: Scope) -> Hashable:
        if dependant_scope is False:
            return False
        elif dependant_scope is None:
            return self._scopes[-1]  # current scope
        else:
            return dependant_scope

    def _task_from_cached_value(
        self, dependant: Dependant, value: DependencyType
    ) -> Task[Callable[[], DependencyType]]:
        async def retrieve():
            return value

        return Task(dependant=dependant, call=retrieve, dependencies={})

    def _check_scope(self, scope: Scope):
        if scope is False:
            return
        if len(self._stacks) == 0:
            raise UnknownScopeError(
                "No current scope in container."
                " You must set a scope before you can execute or resolve any dependencies."
            )
        if scope not in self._stacks:  # self._stacks is just an O(1) lookup of current scopes
            raise UnknownScopeError(
                f"Scope {scope} is not known. Did you forget to enter it? Known scopes: {self._scopes}"
            )

    def _build_task(
        self,
        *,
        dependant: Dependant[DependencyProviderType[DependencyType]],
        task_cache: Dict[Dependant[DependencyProvider], Task[DependencyProvider]],
        call_cache: Dict[DependencyProvider, Dependant[DependencyProvider]],
    ) -> Tuple[bool, Task[DependencyType]]:

        if dependant.call in self._binds:
            dependant = self._binds[dependant.call]

        scope = self._resolve_scope(dependant.scope)
        self._check_scope(scope)

        if scope is not False:
            if dependant.call in call_cache:
                other = call_cache[dependant.call]
                if self._resolve_scope(other.scope) != self._resolve_scope(dependant.scope):
                    raise DuplicatedDependencyError(
                        f"{other.call} is declared as a dependency multiple"
                        " times in the same dependency graph under different scopes"
                    )
                dependant = other
            else:
                call_cache[dependant.call] = dependant

        if dependant in task_cache:
            return True, task_cache[dependant]  # type: ignore

        scope = self._resolve_scope(dependant.scope)
        self._check_scope(scope)
        call = wrap_call(dependant.call, self._stacks[scope if scope is not False else self._scopes[-1]])

        subtasks = {}
        allow_cache = True
        for param_name, sub_dependant in dependant.dependencies.items():
            if sub_dependant in task_cache:
                subtask = task_cache[sub_dependant]
            else:
                allow_cache, subtask = self._build_task(
                    dependant=sub_dependant, task_cache=task_cache, call_cache=call_cache
                )
                task_cache[sub_dependant] = subtask
            subtasks[param_name] = subtask

        if allow_cache and scope is not False:
            # try to get cached value
            for cache_scope in self._scopes:
                cached_values = self._cached_values[cache_scope]
                if dependant.call in cached_values:
                    value = cached_values[dependant.call]
                    task = self._task_from_cached_value(dependant, value)
                    task_cache[dependant] = task
                    return True, task  # type: ignore

        task = Task(dependant=dependant, call=call, dependencies=subtasks)  # type: ignore
        task_cache[dependant] = task
        return False, task  # type: ignore

    @overload
    async def execute(self, dependant: Dependant[AsyncGeneratorProvider[DependencyType]]) -> DependencyType:
        ...

    @overload
    async def execute(self, dependant: Dependant[CoroutineProvider[DependencyType]]) -> DependencyType:
        ...

    @overload
    async def execute(self, dependant: Dependant[GeneratorProvider[DependencyType]]) -> DependencyType:
        ...

    @overload
    async def execute(self, dependant: Dependant[CallableProvider[DependencyType]]) -> DependencyType:
        ...

    async def execute(self, dependant: Dependant) -> Dependency:
        task_cache: Dict[Dependant[DependencyProvider], Task[DependencyProvider]] = {}
        use_cache, task = self._build_task(dependant=dependant, task_cache=task_cache, call_cache={})
        result = await task.result()
        scope = self._resolve_scope(task.dependant.scope)
        if scope is not False:
            self._cached_values[scope][task.dependant.call] = result
        for subtask in task_cache.values():
            scope = self._resolve_scope(subtask.dependant.scope)
            if scope is not False:
                self._cached_values[scope][subtask.dependant.call] = await subtask.result()
        return result

    @overload
    def get_dependant(
        self, call: AsyncGeneratorProvider[DependencyType]
    ) -> Dependant[AsyncGeneratorProvider[DependencyType]]:
        ...

    @overload
    def get_dependant(self, call: CoroutineProvider[DependencyType]) -> Dependant[CoroutineProvider[DependencyType]]:
        ...

    @overload
    def get_dependant(self, call: GeneratorProvider[DependencyType]) -> Dependant[GeneratorProvider[DependencyType]]:
        ...

    @overload
    def get_dependant(self, call: CallableProvider[DependencyType]) -> Dependant[CallableProvider[DependencyType]]:
        ...

    def get_dependant(self, call: DependencyProvider) -> Dependant[DependencyProvider]:  # type: ignore
        return Dependant(call=call)
