from __future__ import annotations

from typing import Any, Iterable, TypeVar

from di.api.dependencies import CacheKey, DependencyParameter, DependentBase

T = TypeVar("T")


class JoinedDependent(DependentBase[T]):
    """A Dependent that aggregates other dependents without directly depending on them"""

    __slots__ = ("dependent", "siblings")

    def __init__(
        self,
        dependent: DependentBase[T],
        *,
        siblings: Iterable[DependentBase[Any]],
    ) -> None:
        self.call = dependent.call
        self.dependent = dependent
        self.siblings = siblings
        self.scope = dependent.scope
        self.use_cache = dependent.use_cache

    def get_dependencies(self) -> list[DependencyParameter]:
        """Get the dependencies of our main dependent and all siblings"""
        return [
            *self.dependent.get_dependencies(),
            *(DependencyParameter(dep, None) for dep in self.siblings),
        ]

    @property
    def cache_key(self) -> CacheKey:
        return (self.dependent.cache_key, tuple(s.cache_key for s in self.siblings))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(dependent={self.dependent}, siblings={self.siblings})"
