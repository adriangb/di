from __future__ import annotations

import inspect
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Coroutine,
    Dict,
    Generator,
    Hashable,
    Optional,
    Protocol,
    TypeVar,
    Union,
    cast,
    overload,
    runtime_checkable,
)

from di._docstrings import join_docstring_from
from di._inspect import DependencyParameter, get_parameters, infer_call_from_annotation
from di.exceptions import WiringError

DependencyType = TypeVar("DependencyType")

CallableProvider = Callable[..., DependencyType]
CoroutineProvider = Callable[..., Coroutine[Any, Any, DependencyType]]
GeneratorProvider = Callable[..., Generator[DependencyType, None, None]]
AsyncGeneratorProvider = Callable[..., AsyncGenerator[DependencyType, None]]

DependencyProviderType = Union[
    CallableProvider[DependencyType],
    CoroutineProvider[DependencyType],
    GeneratorProvider[DependencyType],
    AsyncGeneratorProvider[DependencyType],
]

Scope = Hashable

Dependency = Any

DependencyProvider = Union[
    AsyncGeneratorProvider[Dependency],
    CoroutineProvider[Dependency],
    GeneratorProvider[Dependency],
    CallableProvider[Dependency],
]


_VARIABLE_PARAMETER_KINDS = (
    inspect.Parameter.VAR_POSITIONAL,
    inspect.Parameter.VAR_KEYWORD,
)


_expected_attributes = ("call", "scope", "shared", "get_dependencies", "is_equivalent")


def _is_dependant_protocol_instance(o: object) -> bool:
    # run cheap attribute checks before running isinstance
    # isinstace is expensive since runs reflection on methods
    # to check argument types, etc.
    for attr in _expected_attributes:
        if not hasattr(o, attr):
            return False
    return isinstance(o, DependantProtocol)


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


class Dependant(DependantProtocol[DependencyType]):
    @overload
    def __init__(
        self,
        call: Optional[AsyncGeneratorProvider[DependencyType]] = None,
        scope: Optional[Scope] = None,
        shared: bool = True,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[CoroutineProvider[DependencyType]] = None,
        scope: Optional[Scope] = None,
        shared: bool = True,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[GeneratorProvider[DependencyType]] = None,
        scope: Optional[Scope] = None,
        shared: bool = True,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[CallableProvider[DependencyType]] = None,
        scope: Optional[Scope] = None,
        shared: bool = True,
    ) -> None:
        ...

    def __init__(
        self,
        call: Optional[DependencyProviderType[DependencyType]] = None,
        scope: Scope = None,
        shared: bool = True,
    ) -> None:
        self.call = call
        self.scope = scope
        self.dependencies: Optional[
            Dict[str, DependencyParameter[DependantProtocol[Any]]]
        ] = None
        self.shared = shared

    @join_docstring_from(DependantProtocol[Any].create_sub_dependant)
    def create_sub_dependant(
        self, call: DependencyProvider, scope: Scope, shared: bool
    ) -> DependantProtocol[Any]:
        return Dependant[Any](call=call, scope=scope, shared=shared)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(call={self.call}, scope={self.scope})"

    @join_docstring_from(DependantProtocol[Any].__hash__)
    def __hash__(self) -> int:
        return hash(self.call)

    @join_docstring_from(DependantProtocol[Any].__eq__)
    def __eq__(self, o: object) -> bool:
        if type(self) != type(o):
            return False
        assert isinstance(o, type(self))
        return self.call is o.call

    @join_docstring_from(DependantProtocol[Any].is_equivalent)
    def is_equivalent(self, other: DependantProtocol[Any]) -> bool:
        return self.call is other.call and other.scope == self.scope

    @join_docstring_from(DependantProtocol[Any].get_dependencies)
    def get_dependencies(
        self,
    ) -> Dict[str, DependencyParameter[DependantProtocol[Any]]]:
        if self.dependencies is None:  # type: ignore
            self.dependencies = self.gather_dependencies()
        return self.dependencies

    @join_docstring_from(DependantProtocol[Any].gather_parameters)
    def gather_parameters(self) -> Dict[str, inspect.Parameter]:
        assert self.call is not None, "Cannot gather parameters without a bound call"
        return get_parameters(self.call)

    @join_docstring_from(DependantProtocol[Any].infer_call_from_annotation)
    def infer_call_from_annotation(
        self, param: inspect.Parameter
    ) -> DependencyProvider:
        if param.annotation is param.empty:
            raise WiringError(
                "Cannot wire a parameter with no default and no type annotation"
            )
        return infer_call_from_annotation(param)

    def gather_dependencies(
        self,
    ) -> Dict[str, DependencyParameter[DependantProtocol[Any]]]:
        """Collect this dependencies sub dependencies.

        The returned dict corresponds to keyword arguments that will be passed
        to this dependencies `call` after all sub-dependencies are themselves resolved.
        """
        assert (
            self.call is not None
        ), "Container should have assigned call; this is a bug!"
        res: Dict[str, DependencyParameter[DependantProtocol[Any]]] = {}
        for param_name, param in self.gather_parameters().items():
            if param.kind in _VARIABLE_PARAMETER_KINDS:
                raise WiringError(
                    "Dependencies may not use variable positional or keyword arguments"
                )
            if _is_dependant_protocol_instance(param.default):
                sub_dependant = cast(DependantProtocol[Any], param.default)
                if sub_dependant.call is None:
                    sub_dependant.call = sub_dependant.infer_call_from_annotation(param)
            elif param.default is param.empty:
                sub_dependant = self.create_sub_dependant(
                    call=self.infer_call_from_annotation(param),
                    scope=self.scope,
                    shared=self.shared,
                )
            else:
                continue  # pragma: no cover
            res[param_name] = DependencyParameter(
                dependency=sub_dependant, parameter=param
            )
        return res
