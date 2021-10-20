from __future__ import annotations

import dataclasses
from typing import Any, Generic, List, Mapping, Set

from di._task import Task
from di.types.dependencies import DependantProtocol, DependencyParameter
from di.types.providers import DependencyType

Dependency = Any


@dataclasses.dataclass
class SolvedDependency(Generic[DependencyType]):
    """Representation of a fully solved dependency.

    A fully solved dependency consists of:
    - A DAG of sub-dependency paramters.
    - A topologically sorted order of execution, where each sublist represents a
    group of dependencies that can be executed in parallel.
    """

    dependency: DependantProtocol[DependencyType]
    dag: Mapping[
        DependantProtocol[Any], List[DependencyParameter[DependantProtocol[Any]]]
    ]
    _tasks: Mapping[DependantProtocol[Any], Task[Any]]
    _dependant_dag: Mapping[DependantProtocol[Any], Set[DependantProtocol[Any]]]

    def get_flat_subdependants(self) -> List[DependantProtocol[Any]]:
        """Get an exhaustive list of all of the dependencies of this dependency,
        in no particular order.
        """
        return list(self.dag.keys() - {self.dependency})
