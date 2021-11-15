from __future__ import annotations

import dataclasses
import typing
from typing import Any, Generic, List, Mapping

from di.types.dependencies import DependantBase, DependencyParameter
from di.types.providers import DependencyType

Dependency = Any


@dataclasses.dataclass
class SolvedDependant(Generic[DependencyType]):
    """Representation of a fully solved dependency as DAG"""

    dependency: DependantBase[DependencyType]
    dag: Mapping[DependantBase[Any], List[DependencyParameter[DependantBase[Any]]]]
    # container_cache can be used by the creating container to store data that is tied
    # to the SolvedDependant
    container_cache: typing.Any = None

    def get_flat_subdependants(self) -> List[DependantBase[Any]]:
        """Get an exhaustive list of all of the dependencies of this dependency,
        in no particular order.
        """
        return list(self.dag.keys() - {self.dependency})
