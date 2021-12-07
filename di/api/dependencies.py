from __future__ import annotations

import abc
import inspect
from typing import Any, Generic, List, NamedTuple, Optional, TypeVar

from di.api.providers import DependencyProviderType
from di.api.scopes import Scope

DependencyType = TypeVar("DependencyType")


T = TypeVar("T")


class DependantBase(Generic[DependencyType], metaclass=abc.ABCMeta):
    """A dependant is an object that can provide the container with:
    - A hash, to compare itself against other dependants
    - A scope
    - A callable who's returned value is the dependency
    """

    __slots__ = ("call", "scope", "share")

    call: Optional[DependencyProviderType[DependencyType]]
    scope: Scope
    share: bool

    @abc.abstractmethod
    def __hash__(self) -> int:
        """Dependencies need to be hashable for quick O(1) lookups.

        Generally, hash(self.call) will suffice so that dependencies are identified by their callable.
        """
        pass  # pragma: no cover

    @abc.abstractmethod
    def __eq__(self, o: object) -> bool:
        """Used in conjunction with __hash__ for mapping lookups of dependencies.

        If this returns `True`, the two dependencies are considered the same and
        `di` will pick one to subsitute for the other.

        Note that using the same dependency in two different scopes is prohibited,
        so if this returns `True` and `self.scope != o.scope` `di` will raise a SolvingError.
        """
        pass  # pragma: no cover

    @abc.abstractmethod
    def get_dependencies(
        self,
    ) -> List[DependencyParameter]:
        """Collect all of the sub dependencies for this dependant"""
        pass  # pragma: no cover

    @abc.abstractmethod
    def register_parameter(
        self: DependantBase[T], param: inspect.Parameter
    ) -> DependantBase[T]:
        """Called by the parent so that us / this / the child can register
        the parameter it is attached to.

        If this is an autowired Dependant, this can be used to register self.call.

        This can also be used for recording type annotations or parameter names.

        This method may return the same instance or another DependantBase altogether.
        """
        pass  # pragma: no cover

    def __repr__(self) -> str:
        share = "" if self.share is False else ", share=True"
        return f"{self.__class__.__name__}(call={self.call}, scope={self.scope}{share})"


class DependencyParameter(NamedTuple):
    dependency: DependantBase[Any]
    parameter: Optional[inspect.Parameter]
