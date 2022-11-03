import typing
from typing import Any, Generic, Iterable, Mapping, TypeVar

from di.api.dependencies import DependencyParameter, DependentBase

Dependency = Any

DependencyType = TypeVar("DependencyType")


class SolvedDependent(Generic[DependencyType]):
    """Representation of a fully solved dependency as DAG.

    A SolvedDependent could be a user's endpoint/controller function.
    """

    __slots__ = ("dependency", "dag", "container_cache")

    dependency: DependentBase[DependencyType]
    dag: Mapping[DependentBase[Any], Iterable[DependencyParameter]]
    # container_cache can be used by the creating container to store data that is tied
    # to the SolvedDependent
    container_cache: typing.Any

    def __init__(
        self,
        dependency: DependentBase[DependencyType],
        dag: Mapping[DependentBase[Any], Iterable[DependencyParameter]],
        container_cache: typing.Any,
    ):
        self.dependency = dependency
        self.dag = dag
        self.container_cache = container_cache
