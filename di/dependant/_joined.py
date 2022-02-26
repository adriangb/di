from __future__ import annotations

from typing import Any, Iterable, List, TypeVar

from di.api.dependencies import CacheKey, DependantBase, DependencyParameter

T = TypeVar("T")


class JoinedDependant(DependantBase[T]):
    """A Dependant that aggregates other dependants without directly depending on them"""

    __slots__ = ("dependant", "siblings")

    def __init__(
        self,
        dependant: DependantBase[T],
        *,
        siblings: Iterable[DependantBase[Any]],
    ) -> None:
        self.call = dependant.call
        self.dependant = dependant
        self.siblings = siblings
        self.scope = dependant.scope
        self.use_cache = dependant.use_cache

    def get_dependencies(self) -> List[DependencyParameter]:
        """Get the dependencies of our main dependant and all siblings"""
        return [
            *self.dependant.get_dependencies(),
            *(DependencyParameter(dep, None) for dep in self.siblings),
        ]

    @property
    def cache_key(self) -> CacheKey:
        return (self.dependant.cache_key, tuple((s.cache_key for s in self.siblings)))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(dependant={self.dependant}, siblings={self.siblings})"
