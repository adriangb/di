from __future__ import annotations

import inspect
import sys
from typing import Any, Generic, List, NamedTuple, Optional, TypeVar

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

from di.api.providers import DependencyProviderType
from di.api.scopes import Scope

T = TypeVar("T")


class CacheKey(Protocol):
    def __hash__(self) -> int:
        ...

    def __eq__(self, __o: object) -> bool:
        ...


class DependantBase(Generic[T]):
    """A dependant is an object that can provide the container with:
    - A hash, to compare itself against other dependants
    - A scope
    - A callable who's returned value is the dependency
    """

    __slots__ = ("call", "scope", "share")

    call: Optional[DependencyProviderType[T]]
    scope: Scope
    share: bool

    @property
    def cache_key(self) -> CacheKey:
        raise NotImplementedError

    def get_dependencies(self) -> List[DependencyParameter]:
        """Collect all of the sub dependencies for this dependant"""
        raise NotImplementedError

    def register_parameter(self, param: inspect.Parameter) -> DependantBase[Any]:
        """Called by the parent so that us / this / the child can register
        the parameter it is attached to.

        This is used to register self.call,
        but can also be used for recording type annotations or parameter names.

        This method may return the same instance or another DependantBase altogether.
        """
        raise NotImplementedError


class DependencyParameter(NamedTuple):
    dependency: DependantBase[Any]
    parameter: Optional[inspect.Parameter]
