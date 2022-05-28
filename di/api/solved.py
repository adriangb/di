import typing
from typing import Any, Generic, Iterable, Mapping, TypeVar

from di.api.dependencies import DependantBase, DependencyParameter

Dependency = Any

DependencyType = TypeVar("DependencyType")


class SolvedDependant(Generic[DependencyType]):
    """Representation of a fully solved dependency as DAG"""

    __slots__ = ("dependency", "dag", "container_cache")

    dependency: DependantBase[DependencyType]
    dag: Mapping[DependantBase[Any], Iterable[DependencyParameter]]
    # container_cache can be used by the creating container to store data that is tied
    # to the SolvedDependant
    container_cache: typing.Any

    def __init__(
        self,
        dependency: DependantBase[DependencyType],
        dag: Mapping[DependantBase[Any], Iterable[DependencyParameter]],
        container_cache: typing.Any,
    ):
        self.dependency = dependency
        self.dag = dag
        self.container_cache = container_cache
