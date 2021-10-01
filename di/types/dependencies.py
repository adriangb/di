from __future__ import annotations

import inspect
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from di._inspect import DependencyParameter
from di.types.providers import (
    DependencyProvider,
    DependencyProviderType,
    DependencyType,
)
from di.types.scopes import Scope


@runtime_checkable
class DependantProtocol(Protocol[DependencyType]):
    """A dependant is an object that can provide the container with:
    - A hash, to compare itself against other dependants
    - A scope
    - A callable that can be used to assemble itself
    - The dependants that correspond to the keyword arguments of that callable
    """

    call: Optional[DependencyProviderType[DependencyType]]
    dependencies: Optional[Dict[str, DependencyParameter[DependantProtocol[Any]]]]
    scope: Scope
    share: bool

    def __hash__(self) -> int:
        """Dependencies need to be hashable for quick O(1) lookups.

        Generally, hash(self.call) will suffice so that dependencies are identified by their callable.
        """
        raise NotImplementedError

    def __eq__(self, o: object) -> bool:
        """Used in conjunction with __hash__ for mapping lookups of dependencies.

        If this returns `True`, the two dependencies are considered the same and
        `di` will pick one to subsitute for the other.

        Note that using the same dependenyc in two different scopes is prohibited,
        so if this returns `True` and `self.scope != o.scope` `di` will raise a DependencyRegistryError.
        """
        raise NotImplementedError

    def get_dependencies(
        self,
    ) -> Dict[str, DependencyParameter[DependantProtocol[Any]]]:
        """Collect all of the sub dependencies for this dependant into a mapping
        of parameter name => parameter spec.
        """
        raise NotImplementedError

    def infer_call_from_annotation(
        self, param: inspect.Parameter
    ) -> DependencyProvider:
        """Called when the dependency was not explicitly passed a callable.

        It is important to note that param in this context refers to the parameter in this
        Dependant's parent.
        For example, in the case of `def func(thing: Something = Dependency())` this method
        will be called with a Parameter corresponding to Something.
        """
        raise NotImplementedError
