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
    shared: bool

    def __hash__(self) -> int:
        """A unique identifier for this dependency.

        By default, dependencies are identified by their call attribute.
        This can be overriden to introduce other semantics, e.g. to involve the scope or custom attrbiutes
        in dependency identification.
        """
        raise NotImplementedError

    def __eq__(self, o: object) -> bool:
        """Used in conjunction with __hash__ for mapping lookups of dependencies.
        Generally, this should have the same semantics as __hash__ but can check for object identity.
        """
        raise NotImplementedError

    def is_equivalent(self, other: DependantProtocol[Any]) -> bool:
        """Copare two DependantProtocol implementers for equality.

        By default, the two are equal only if they share the same callable and scope.

        If two dependencies share the same hash but are not equal, the Container will
        report an error.
        This is commonly caused by using the same callable under two different scopes.
        To remedy this, you can either wrap the callable to give it two different hashes/ids,
        or you can create a DependantProtocol implementation that overrides __hash__ and/or __eq__.
        """
        raise NotImplementedError

    def get_dependencies(
        self,
    ) -> Dict[str, DependencyParameter[DependantProtocol[Any]]]:
        """A cache on top of `gather_dependencies()`"""
        raise NotImplementedError

    def gather_parameters(self) -> Dict[str, inspect.Parameter]:
        """Collect parameters that this dependency needs to construct itself.

        Generally, this means introspecting into this dependencies own callable.
        """
        raise NotImplementedError

    def create_sub_dependant(
        self, call: DependencyProvider, scope: Scope, shared: bool
    ) -> DependantProtocol[Any]:
        """Create a Dependant instance from a sub-dependency of this Dependency.

        This is used in the scenario where a transient dependency is inferred from a type hint.
        For example:
        >>> class Foo:
        >>>     ...
        >>> def foo_factory(foo: Foo) -> Foo:
        >>>     return foo
        >>> def parent(foo: Dependency(foo_factory)):
        >>>    ...
        In this scenario, `Dependency(foo_factory)` will call `create_sub_dependant(Foo)`.
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
