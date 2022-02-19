from __future__ import annotations

import inspect
import sys
from typing import Any, Generic, List, NamedTuple, Optional, TypeVar

if sys.version_info < (3, 8):
    from typing_extensions import Protocol, runtime_checkable
else:
    from typing import Protocol, runtime_checkable

from di._utils.types import CacheKey
from di.api._providers import DependencyProviderType
from di.api.scopes import Scope

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


__all__ = (
    "CacheKey",
    "DependantBase",
    "DependencyParameter",
    "InjectableClassProvider",
)


@runtime_checkable
class InjectableClassProvider(Protocol[T_co]):
    @classmethod
    def __di_dependency__(cls) -> MarkerBase:
        ...


class DependantBase(Generic[T]):
    """A dependant is an object that can provide the container with:
    - A hash, to compare itself against other dependants
    - A scope
    - A callable who's returned value is the dependency
    """

    call: Optional[DependencyProviderType[T]]
    scope: Scope
    use_cache: bool

    @property
    def cache_key(self) -> CacheKey:
        raise NotImplementedError

    def get_dependencies(self) -> List[DependencyParameter]:
        """Collect all of the sub dependencies for this dependant"""
        raise NotImplementedError


class MarkerBase:
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
