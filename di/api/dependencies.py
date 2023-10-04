import inspect
from typing import (
    Any,
    Generic,
    List,
    NamedTuple,
    Optional,
    Protocol,
    TypeVar,
    runtime_checkable,
)

from di._utils.types import CacheKey
from di.api.providers import DependencyProviderType
from di.api.scopes import Scope

T = TypeVar("T")


__all__ = (
    "CacheKey",
    "DependentBase",
    "DependencyParameter",
    "InjectableClassProvider",
)


@runtime_checkable
class InjectableClassProvider(Protocol):
    @classmethod
    def __di_dependency__(cls, param: inspect.Parameter) -> "DependentBase[Any]":
        ...


class DependentBase(Generic[T]):
    """A dependent is an object that can provide the container with:
    - A hash, to compare itself against other dependents
    - A scope
    - A callable who's returned value is the dependency
    """

    call: Optional[DependencyProviderType[T]]
    scope: Scope
    use_cache: bool

    @property
    def cache_key(self) -> CacheKey:
        raise NotImplementedError

    def get_dependencies(self) -> "List[DependencyParameter]":
        """Collect all of the sub dependencies for this dependent"""
        raise NotImplementedError


class DependencyParameter(NamedTuple):
    dependency: DependentBase[Any]
    parameter: Optional[inspect.Parameter]
