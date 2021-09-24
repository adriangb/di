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
    List,
    Optional,
    Protocol,
    TypeVar,
    Union,
    cast,
    overload,
    runtime_checkable,
)

from anydep._identity_containers import IdentitySet
from anydep._inspect import get_parameters, infer_call_from_annotation
from anydep._parameters import DependencyParameter, ParameterKind
from anydep.exceptions import WiringError

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
    def dependencies(self) -> Optional[Dict[str, DependencyParameter]]:
        raise NotImplementedError

    @dependencies.setter
    def dependencies(self, dependencies: Dict[str, DependencyParameter]) -> None:
        raise NotImplementedError

    @property
    def solved_dependencies(self) -> Optional[List[List[DependantProtocol[Any]]]]:
        raise NotImplementedError

    @solved_dependencies.setter
    def solved_dependencies(self, solved: List[List[DependantProtocol[Any]]]) -> None:
        raise NotImplementedError

    @property
    def parents(self) -> IdentitySet[DependantProtocol[Any]]:
        raise NotImplementedError

    def __hash__(self) -> int:
        """A unique identifier for this dependency.

        By default, dependencies are identified by their call attribute.
        This can be overriden to introduce other semantics, e.g. to involve the scope or custom attrbiutes
        in dependency identification.
        """
        return hash(self.call)

    def get_dependencies(self) -> Dict[str, DependencyParameter]:
        """A cache on top of `gather_dependencies()`"""
        if self.dependencies is None:
            self.dependencies = self.gather_dependencies()
        return self.dependencies

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

    def gather_dependencies(self) -> Dict[str, DependencyParameter]:
        """Collect this dependencies sub dependencies.

        The returned dict corresponds to keyword arguments that will be passed
        to this dependencies `call` after all sub-dependencies are themselves resolved.
        """
        assert (
            self.call is not None
        ), "Container should have assigned call; this is a bug!"
        res: Dict[str, DependencyParameter] = {}
        for param_name, param in self.gather_parameters().items():
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
            if param.kind in (param.kind.VAR_KEYWORD, param.kind.VAR_KEYWORD):
                raise TypeError(
                    "Dependencies may not use variable positional or keyword arguments"
                )
            if param.kind is param.POSITIONAL_ONLY:
                kind = ParameterKind.positional
            else:
                kind = ParameterKind.keyword
            res[param_name] = DependencyParameter(dependency=sub_dependant, kind=kind)
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
    @overload
    def __init__(
        self,
        call: Optional[AsyncGeneratorProvider[DependencyType]] = None,
        scope: Optional[Scope] = None,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[CoroutineProvider[DependencyType]] = None,
        scope: Optional[Scope] = None,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[GeneratorProvider[DependencyType]] = None,
        scope: Optional[Scope] = None,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[CallableProvider[DependencyType]] = None,
        scope: Optional[Scope] = None,
    ) -> None:
        ...

    def __init__(
        self,
        call: Optional[DependencyProviderType[DependencyType]] = None,
        scope: Optional[Scope] = None,
    ) -> None:
        self._call = call
        self._scope = scope
        self._solved_dependencies: Optional[List[List[DependantProtocol[Any]]]] = None
        self._parents: IdentitySet[DependantProtocol[Any]] = IdentitySet()
        self._dependencies: Dict[str, DependencyParameter] = dict()

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

    @property
    def parents(self) -> IdentitySet[DependantProtocol[Any]]:
        return self._parents

    @property
    def dependencies(self) -> Optional[Dict[str, DependencyParameter]]:
        return self._dependencies

    @dependencies.setter
    def dependencies(self, dependencies: Dict[str, DependencyParameter]) -> None:
        self._dependencies = dependencies

    def create_sub_dependant(self, call: DependencyProvider) -> DependantProtocol[Any]:
        return Dependant[Any](call=call)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(call={self.call}, scope={self.scope})"
