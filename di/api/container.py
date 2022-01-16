import sys
from typing import Any, Collection, ContextManager, Mapping, Optional, TypeVar

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

from di._utils.types import FusedContextManager
from di.api.dependencies import DependantBase
from di.api.executor import AsyncExecutorProtocol, SyncExecutorProtocol
from di.api.providers import DependencyProvider, DependencyProviderType
from di.api.scopes import Scope
from di.api.solved import SolvedDependant

ContainerType = TypeVar("ContainerType")

DependencyType = TypeVar("DependencyType")


class ContainerProtocol(Protocol):
    @property
    def scopes(self) -> Collection[Scope]:
        ...

    def bind(
        self,
        provider: DependantBase[Any],
        dependency: DependencyProviderType[Any],
    ) -> ContextManager[None]:
        """Bind a new dependency provider for a given dependency.

        This can be used as a function (for a permanent bind, cleared when `scope` is exited)
        or as a context manager (the bind will be cleared when the context manager exits).

        Binds are only identified by the identity of the callable and do not take into account
        the scope or any other data from the dependency they are replacing.
        """
        ...

    def solve(
        self,
        dependency: DependantBase[DependencyType],
    ) -> SolvedDependant[DependencyType]:
        """Solve a dependency.

        Returns a SolvedDependant that can be executed to get the dependency's value.
        """
        ...

    def enter_scope(
        self: ContainerType, scope: Scope
    ) -> FusedContextManager[ContainerType]:
        """Enter a scope and get back a new BaseContainer in that scope"""
        ...

    def execute_sync(
        self,
        solved: SolvedDependant[DependencyType],
        executor: SyncExecutorProtocol,
        *,
        values: Optional[Mapping[DependencyProvider, Any]] = None,
    ) -> DependencyType:
        """Execute an already solved dependency.

        This method may or may not be able to handle async dependencies,
        this is up to the executor passed in.
        """
        ...

    async def execute_async(
        self,
        solved: SolvedDependant[DependencyType],
        *,
        executor: AsyncExecutorProtocol,
        values: Optional[Mapping[DependencyProvider, Any]] = None,
    ) -> DependencyType:
        """Execute an already solved dependency.

        This method can always handle sync and async dependencies.
        """
        ...
