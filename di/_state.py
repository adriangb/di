from __future__ import annotations

from contextlib import AsyncExitStack, ExitStack, contextmanager
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    ContextManager,
    Dict,
    Generator,
    List,
    Optional,
    Type,
    Union,
    cast,
)

from di._scope_map import ScopeMap
from di.types import FusedContextManager
from di.types.dependencies import DependantProtocol
from di.types.providers import (
    DependencyProvider,
    DependencyProviderType,
    DependencyType,
)
from di.types.scopes import Scope


class ContainerState(object):

    __slots__ = ("binds", "cached_values", "stacks")

    def __init__(self) -> None:
        self.binds: Dict[DependencyProvider, DependantProtocol[Any]] = {}
        self.cached_values = ScopeMap[DependencyProvider, Any]()
        self.stacks: Dict[Scope, Union[AsyncExitStack, ExitStack]] = {}

    def copy(self) -> "ContainerState":
        new = ContainerState()
        new.binds = self.binds.copy()
        new.stacks = self.stacks.copy()
        new.cached_values = self.cached_values.copy()
        return new

    def enter_scope(self, scope: Scope) -> FusedContextManager[None]:
        return ScopeContext(self, scope)

    @property
    def scopes(self) -> List[Scope]:
        return list(self.stacks.keys())

    def bind(
        self,
        provider: DependantProtocol[DependencyType],
        dependency: DependencyProviderType[DependencyType],
    ) -> ContextManager[None]:
        previous_provider = self.binds.get(dependency, None)

        self.binds[dependency] = provider

        @contextmanager
        def unbind() -> Generator[None, None, None]:
            try:
                yield
            finally:
                self.binds.pop(dependency)
                if previous_provider is not None:
                    self.binds[dependency] = previous_provider

        return unbind()


class ScopeContext(FusedContextManager[None]):
    def __init__(self, state: ContainerState, scope: Scope) -> None:
        self.state = state
        self.scope = scope

    def __enter__(self):
        self.state.stacks[self.scope] = ExitStack()
        self.state.cached_values.add_scope(self.scope)

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        stack = self.state.stacks[self.scope]
        if TYPE_CHECKING:
            stack = cast(ExitStack, stack)
        self.state.stacks.pop(self.scope)
        self.state.cached_values.pop_scope(self.scope)
        return stack.__exit__(exc_type, exc_value, traceback)

    async def __aenter__(self):
        self.state.stacks[self.scope] = AsyncExitStack()
        self.state.cached_values.add_scope(self.scope)

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        stack = self.state.stacks[self.scope]
        if TYPE_CHECKING:
            stack = cast(AsyncExitStack, stack)
        self.state.stacks.pop(self.scope)
        self.state.cached_values.pop_scope(self.scope)
        return await stack.__aexit__(exc_type, exc_value, traceback)
