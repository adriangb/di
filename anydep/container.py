from contextlib import AsyncExitStack, asynccontextmanager
from contextvars import ContextVar
from typing import (
    AsyncGenerator,
    Callable,
    Dict,
    Hashable,
    List,
    Mapping,
    Optional,
    Tuple,
    cast,
    overload,
)

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


class ContainerState:
    def __init__(self) -> None:
        self.binds: Dict[DependencyProvider, Dependant[DependencyProvider]] = {}
        self.cached_values: Dict[Hashable, Dict[DependencyProvider, Dependency]] = {}
        self.stacks: Dict[Scope, AsyncExitStack] = {}
        self.scopes: List[Scope] = []

    def copy(self) -> "ContainerState":
        new = ContainerState()
        new.binds = self.binds.copy()
        new.cached_values = {k: v.copy() for k, v in self.cached_values.items()}
        new.stacks = self.stacks.copy()
        new.scopes = self.scopes.copy()
        return new

    @asynccontextmanager
    async def enter_scope(self, scope: Scope) -> AsyncGenerator[None, None]:
        if scope in self.stacks:
            raise DuplicateScopeError(f"Scope {scope} has already been entered!")
        async with AsyncExitStack() as stack:
            self.scopes.append(scope)
            self.stacks[scope] = stack
            bound_providers = self.binds
            self.binds = bound_providers.copy()
            self.cached_values[scope] = {}
            try:
                yield
            finally:
                self.stacks.pop(scope)
                self.binds = bound_providers
                self.cached_values.pop(scope)
                self.scopes.pop()


class Container:
    def __init__(self) -> None:
        self.context = ContextVar[ContainerState]("context")
        state = ContainerState()
        self.context.set(state)

    @property
    def state(self) -> ContainerState:
        return self.context.get()

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
        self.state.binds[target] = Dependant(source)  # type: ignore
        for cached_values in self.state.cached_values.values():
            if target in cached_values:
                cached_values.pop(target)

    @asynccontextmanager
    async def enter_global_scope(self, scope: Scope) -> AsyncGenerator[None, None]:
        async with self.state.enter_scope(scope):
            yield

    @asynccontextmanager
    async def enter_local_scope(self, scope: Scope) -> AsyncGenerator[None, None]:
        current = self.state
        new = current.copy()
        token = self.context.set(new)
        try:
            async with self.state.enter_scope(scope):
                yield
        finally:
            self.context.reset(token)

    def _get_scope_index(self, scope: Scope) -> int:
        self._check_scope(scope)
        return self.state.scopes.index(scope)

    def _resolve_scope(self, dependant_scope: Scope) -> Hashable:
        if dependant_scope is False:
            return False
        elif dependant_scope is None:
            return self.state.scopes[-1]  # current scope
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
        if len(self.state.stacks) == 0:
            raise UnknownScopeError(
                "No current scope in container."
                " You must set a scope before you can execute or resolve any dependencies."
            )
        if scope not in self.state.stacks:  # self._stacks is just an O(1) lookup of current scopes
            raise UnknownScopeError(
                f"Scope {scope} is not known. Did you forget to enter it? Known scopes: {self.state.scopes}"
            )

    def _build_task(
        self,
        *,
        dependant: Dependant[DependencyProviderType[DependencyType]],
        task_cache: Dict[Dependant[DependencyProvider], Task[DependencyProvider]],
        call_cache: Dict[DependencyProvider, Dependant[DependencyProvider]],
        binds: Mapping[DependencyProvider, DependencyProvider],
    ) -> Tuple[bool, Task[DependencyType]]:

        if dependant.call in binds:
            dependant = binds[dependant.call]  # type: ignore
        elif dependant.call in self.state.binds:
            dependant = self.state.binds[dependant.call]  # type: ignore

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
                call_cache[dependant.call] = dependant  # type: ignore

        if dependant in task_cache:
            return True, task_cache[dependant]  # type: ignore

        scope = self._resolve_scope(dependant.scope)
        self._check_scope(scope)
        call = wrap_call(
            cast(Callable[..., DependencyProvider], dependant.call),
            self.state.stacks[scope if scope is not False else self.state.scopes[-1]],
        )

        subtasks = {}
        allow_cache = True
        for param_name, sub_dependant in dependant.dependencies.items():
            if sub_dependant in task_cache:
                subtask = task_cache[sub_dependant]
            else:
                allow_cache, subtask = self._build_task(
                    dependant=sub_dependant, task_cache=task_cache, call_cache=call_cache, binds=binds
                )
                task_cache[sub_dependant] = subtask
            subtasks[param_name] = subtask

        if allow_cache and scope is not False:
            # try to get cached value
            for cache_scope in self.state.scopes:
                cached_values = self.state.cached_values[cache_scope]
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

    async def execute(
        self, dependant: Dependant, binds: Optional[Mapping[DependencyProvider, DependencyProvider]] = None
    ) -> Dependency:
        task_cache: Dict[Dependant[DependencyProvider], Task[DependencyProvider]] = {}
        binds = binds or {}
        _, task = self._build_task(dependant=dependant, task_cache=task_cache, call_cache={}, binds=binds)
        result = await task.result()
        scope = self._resolve_scope(task.dependant.scope)
        if scope is not False:
            self.state.cached_values[scope][cast(DependencyProvider, task.dependant.call)] = result
        for subtask in task_cache.values():
            scope = self._resolve_scope(subtask.dependant.scope)
            if scope is not False:
                v = await subtask.result()
                self.state.cached_values[scope][cast(DependencyProvider, subtask.dependant.call)] = v
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
