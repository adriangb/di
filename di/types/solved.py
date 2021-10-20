from __future__ import annotations

import dataclasses
from typing import Any, Generic, List, Mapping, Set

from di._task import Task
from di.types.dependencies import DependantProtocol, DependencyParameter
from di.types.providers import DependencyType

Dependency = Any


@dataclasses.dataclass
class SolvedDependency(Generic[DependencyType]):
    """Representation of a fully solved dependency as DAG"""

    dependency: DependantProtocol[DependencyType]
    dag: Mapping[
        DependantProtocol[Any], List[DependencyParameter[DependantProtocol[Any]]]
    ]
    # the following attributes are used to cache data for solved dependencies
    # they are put on SolvedDependency so that they can be garbage collected along with it
    # these are implementation details and are subject to change at any time
    _tasks: Mapping[DependantProtocol[Any], Task[Any]]
    _dependency_dag: Mapping[DependantProtocol[Any], Set[DependantProtocol[Any]]]

    def get_flat_subdependants(self) -> List[DependantProtocol[Any]]:
        """Get an exhaustive list of all of the dependencies of this dependency,
        in no particular order.
        """
        return list(self.dag.keys() - {self.dependency})
