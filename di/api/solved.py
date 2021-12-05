from __future__ import annotations

import typing
from typing import Any, Generic, Iterable, List, Mapping

from di.api.dependencies import DependantBase, DependencyParameter
from di.api.providers import DependencyType

Dependency = Any


class SolvedDependant(Generic[DependencyType]):
    """Representation of a fully solved dependency as DAG"""

    __slots__ = ("dependency", "dag", "topsort", "container_cache")

    def __init__(
        self,
        dependency: DependantBase[DependencyType],
        dag: Mapping[DependantBase[Any], List[DependencyParameter]],
        # A toplogical sort represented as groups of dependencies that can be executed concurrently
        # This is just one of many possible valid toplogical sorts
        # It is calculated optimistically: this is how dependencies _would_ be executed
        # if all dependencies executed instantly
        topsort: Iterable[Iterable[DependantBase[Any]]],
        # container_cache can be used by the creating container to store data that is tied
        # to the SolvedDependant
        container_cache: typing.Any,
    ):
        self.dependency = dependency
        self.dag = dag
        self.topsort = topsort
        self.container_cache = container_cache

    def get_flat_subdependants(self) -> List[DependantBase[Any]]:
        """Get an exhaustive list of all of the dependencies of this dependency,
        in no particular order.
        """
        return list(self.dag.keys() - {self.dependency})

    def __hash__(self) -> int:
        return id(self)

    def __eq__(self, __o: object) -> bool:
        return __o is self
