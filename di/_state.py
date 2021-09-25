from __future__ import annotations

from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from typing import Any, AsyncGenerator, ContextManager, Dict, Generator, Optional

from di._scope_map import ScopeMap
from di.dependency import DependencyProvider, Scope
from di.exceptions import DuplicateScopeError, UnknownScopeError


class ContainerState:
    def __init__(self) -> None:
        self.binds = ScopeMap[DependencyProvider, DependencyProvider]()
        self.cached_values = ScopeMap[DependencyProvider, Any]()
        self.stacks: Dict[Scope, AsyncExitStack] = {}

    def copy(self) -> "ContainerState":
        new = ContainerState()
        new.binds = self.binds.copy()
        new.stacks = self.stacks.copy()
        new.cached_values = self.cached_values.copy()
        return new

    @asynccontextmanager
    async def enter_scope(self, scope: Scope) -> AsyncGenerator[None, None]:
        if scope in self.stacks:
            raise DuplicateScopeError(f"Scope {scope} has already been entered!")
        stack = AsyncExitStack()
        self.stacks[scope] = stack
        if not self.binds.has_scope(scope):
            self.binds.add_scope(scope)
        self.cached_values.add_scope(scope)
        try:
            yield
        finally:
            await stack.aclose()
            self.stacks.pop(scope)
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
                if previous_provider is not None:
                    self.binds.set(dependency, previous_provider, scope=previous_scope)

        return unbind()

    def get_bound_provider(
        self, dependency: DependencyProvider
    ) -> Optional[DependencyProvider]:
        return self.binds.get(dependency)
