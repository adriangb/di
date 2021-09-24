from __future__ import annotations

import inspect
from functools import cached_property
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    Generator,
    Hashable,
    List,
    Optional,
    Protocol,
    TypeVar,
    Union,
    cast,
    runtime_checkable,
)

from anydep._inspect import get_parameters, infer_call_from_annotation
from anydep.exceptions import WiringError

DependencyType = TypeVar("DependencyType")

CallableProvider = Callable[..., DependencyType]
CoroutineProvider = Callable[..., Awaitable[DependencyType]]
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


@runtime_checkable
class DependantProtocol(Protocol[DependencyType]):
    """A dependant is an object that can provide the container with:
    - A hash, to compare itself against other dependants
    - A scope
    - A callable that can be used to assemble itself
    - The dependants that correspond to the keyword arguments of that callable
    """

    @property
    def scope(self) -> Scope:
        raise NotImplementedError

    @property
    def call(self) -> Optional[DependencyProviderType[DependencyType]]:
        raise NotImplementedError

    @call.setter
    def call(self, call: Optional[DependencyProvider]) -> None:
        raise NotImplementedError

    @property
    def solved_dependencies(self) -> Optional[List[List[DependantProtocol[Any]]]]:
        raise NotImplementedError

    @solved_dependencies.setter
    def solved_dependencies(self, solved: List[List[DependantProtocol[Any]]]) -> None:
        raise NotImplementedError

    def __hash__(self) -> int:
        """A unique identifier for this dependency.

        By default, dependencies are identified by their call attribute.
        """
        return hash(self.call)

    @cached_property
    def parameters(self) -> Dict[str, inspect.Parameter]:
        """A cache on top of `gather_parameters()`"""
        return self.gather_parameters()

    @cached_property
    def dependencies(self) -> Dict[str, DependantProtocol[Any]]:
        """A cache on top of `gather_dependencies()`"""
        return self.gather_dependencies()

    def gather_parameters(self) -> Dict[str, inspect.Parameter]:
        """Collect parameters that this dependency needs to construct itself.

        Generally, this means introspecting into this dependencies own callable.
        """
        assert self.call is not None, "Cannot gather parameters without a bound call"
        return get_parameters(self.call)

    def create_sub_dependant(self, call: DependencyProvider) -> DependantProtocol[Any]:
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

    def gather_dependencies(self) -> Dict[str, DependantProtocol[Any]]:
        """Collect this dependencies sub dependencies.

        The returned dict corresponds to keyword arguments that will be passed
        to this dependencies `call` after all sub-dependencies are themselves resolved.
        """
        assert (
            self.call is not None
        ), "Container should have assigned call; this is a bug!"
        res: Dict[str, DependantProtocol[Any]] = {}
        for param_name, param in self.parameters.items():
            if isinstance(param.default, DependantProtocol):
                sub_dependant = cast(DependantProtocol[Any], param.default)
                if sub_dependant.call is None:
                    sub_dependant.call = sub_dependant.infer_call_from_annotation(param)
            elif param.default is param.empty:
                sub_dependant = self.create_sub_dependant(
                    call=self.infer_call_from_annotation(param)
                )
            else:
                continue  # use default value
            res[param_name] = sub_dependant
        return res

    def infer_call_from_annotation(
        self, param: inspect.Parameter
    ) -> DependencyProvider:
        """Called when the dependency was not explicitly passed a callable.

        It is important to note that param in this context refers to the parameter in this
        Dependant's parent.
        For example, in the case of `def func(thing: Something = Dependency())` this method
        will be called with a Parameter corresponding to Something.
        """
        if param.annotation is param.empty:
            raise WiringError(
                "Cannot wire a parameter with no default and no type annotation"
            )
        return infer_call_from_annotation(param)


class Dependant(DependantProtocol[DependencyType]):
    def __init__(
        self,
        call: Optional[DependencyProviderType[DependencyType]] = None,
        scope: Optional[Scope] = None,
    ) -> None:
        self._call = call
        self._scope = scope
        self._solved_dependencies: Optional[List[List[DependantProtocol[Any]]]] = None

    @property
    def scope(self) -> Scope:
        return self._scope

    @property
    def call(self) -> Optional[DependencyProviderType[DependencyType]]:
        return self._call

    @call.setter
    def call(self, call: Optional[DependencyProvider]) -> None:
        self._call = call

    @property
    def solved_dependencies(self) -> Optional[List[List[DependantProtocol[Any]]]]:
        return self._solved_dependencies

    @solved_dependencies.setter
    def solved_dependencies(self, solved: List[List[DependantProtocol[Any]]]) -> None:
        self._solved_dependencies = solved

    def create_sub_dependant(self, call: DependencyProvider) -> DependantProtocol[Any]:
        return Dependant(call=call)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(call={self.call}, scope={self.scope})"
