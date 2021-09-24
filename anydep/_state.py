from collections import ChainMap
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from typing import (
    Any,
    AsyncGenerator,
    ContextManager,
    Dict,
    Generator,
    Generic,
    Hashable,
    List,
    Mapping,
    Optional,
    TypeVar,
)

from anydep.dependency import DependencyProvider, Scope
from anydep.exceptions import DuplicateScopeError, UnknownScopeError

T = TypeVar("T")
KT = TypeVar("KT", bound=Hashable)
VT = TypeVar("VT")


class ScopeMap(Generic[KT, VT]):
    def __init__(self, *scope_mappings: Mapping[KT, Scope]) -> None:
        self.scope_mapping: ChainMap[KT, Scope] = ChainMap(*scope_mappings)
        self.mappings: Dict[Scope, Dict[KT, VT]] = {}

    def get(self, key: KT) -> VT:
        return self.mappings[self.scope_mapping[key]][key]

    def contains(self, key: KT) -> bool:
        return key in self.scope_mapping

    def get_scope(self, key: KT) -> Scope:
        return self.scope_mapping[key]

    def set(self, key: KT, value: VT, *, scope: Scope) -> None:
        if key in self.scope_mapping:
            current_scope = self.scope_mapping.pop(key)
            self.mappings[current_scope].pop(key)
        self.scope_mapping[key] = scope
        self.mappings[scope][key] = value

    def pop(self, key: KT) -> None:
        if key not in self.scope_mapping:
            raise KeyError
        scope = self.scope_mapping.pop(key)
        self.mappings[scope].pop(key)

    def append_scope(self, scope: Scope) -> None:
        self.mappings[scope] = {}

    def pop_scope(self, scope: Scope) -> None:
        unbound = self.mappings.pop(scope)
        for key in unbound.keys():
            self.scope_mapping.pop(key, None)

    def has_scope(self, scope: Scope) -> bool:
        return scope in self.mappings

    def copy(self) -> "ScopeMap[KT, VT]":
        new = ScopeMap[KT, VT](self.scope_mapping, {})
        new.mappings = self.mappings.copy()
        return new


class ContainerState:
    def __init__(self) -> None:
        self.binds = ScopeMap[DependencyProvider, DependencyProvider]()
        self.cached_values = ScopeMap[DependencyProvider, Any]()
        self.stacks: Dict[Scope, AsyncExitStack] = {}

    @property
    def scopes(self) -> List[Scope]:
        return list(self.stacks.keys())

    def copy(self) -> "ContainerState":
        new = ContainerState()
        new.binds = self.binds.copy()
        new.stacks = self.stacks.copy()
        return new

    @asynccontextmanager
    async def enter_scope(self, scope: Scope) -> AsyncGenerator[None, None]:
        if scope in self.stacks:
            raise DuplicateScopeError(f"Scope {scope} has already been entered!")
        stack = AsyncExitStack()
        self.stacks[scope] = stack
        self.binds.append_scope(scope)
        self.cached_values.append_scope(scope)
        try:
            yield
        finally:
            await stack.aclose()
            self.stacks.pop(scope)
            self.binds.pop_scope(scope)
            self.cached_values.pop_scope(scope)

    def bind(
        self, provider: DependencyProvider, dependency: DependencyProvider, scope: Scope
    ) -> ContextManager[None]:
        if not self.binds.has_scope(scope):
            raise UnknownScopeError(
                f"Scope {scope} is not a known scope. Did you forget to enter it?"
            )
        previous_scope: Optional[Scope]
        previous_provider: Optional[DependencyProvider]
        try:
            previous_provider = self.binds.get(dependency)
            previous_scope = self.binds.get_scope(dependency)
        except KeyError:
            previous_provider = None
            previous_scope = None

        self.binds.set(dependency, provider, scope=scope)
        if self.cached_values.contains(dependency):
            self.cached_values.pop(dependency)

        @contextmanager
        def unbind() -> Generator[None, None, None]:
            try:
                yield
            finally:
                self.binds.pop(dependency)
                if self.cached_values.contains(dependency):
                    self.cached_values.pop(dependency)
                if previous_provider is not None:
                    self.binds.set(dependency, previous_provider, scope=previous_scope)

        return unbind()

    def get_bound_provider(
        self, dependency: DependencyProvider
    ) -> Optional[DependencyProvider]:
        return self.binds.get(dependency)
