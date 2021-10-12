from __future__ import annotations

import dataclasses
from typing import Any, Dict, Generic, List, Union

from di._task import AsyncTask, SyncTask
from di.types.dependencies import DependantProtocol, DependencyParameter
from di.types.providers import Dependency, DependencyType


@dataclasses.dataclass
class SolvedDependency(Generic[DependencyType]):
    """Representation of a fully solved dependency.

    A fully solved dependency consists of:
    - A DAG of sub-dependency paramters.
    - A topologically sorted order of execution, where each sublist represents a
    group of dependencies that can be executed in parallel.
    """

    dependency: DependantProtocol[DependencyType]
    dag: Dict[DependantProtocol[Any], List[DependencyParameter[DependantProtocol[Any]]]]
    _tasks: List[List[Union[AsyncTask[Dependency], SyncTask[Dependency]]]]

    def get_flat_subdependants(self) -> List[DependantProtocol[Any]]:
        """Get an exhaustive list of all of the dependencies of this dependency,
        in no particular order.
        """
        return list(self.dag.keys() - {self.dependency})
