from __future__ import annotations

import inspect
import sys
from typing import Any, Dict, Iterable, List, Optional, Type, overload

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

from di._docstrings import join_docstring_from
from di._inspect import get_parameters, infer_call_from_annotation
from di.exceptions import WiringError
from di.types.dependencies import DependantProtocol, DependencyParameter, T
from di.types.providers import (
    AsyncGeneratorProvider,
    CallableProvider,
    CoroutineProvider,
    DependencyProviderType,
    DependencyType,
    GeneratorProvider,
)
from di.types.scopes import Scope

_VARIABLE_PARAMETER_KINDS = (
    inspect.Parameter.VAR_POSITIONAL,
    inspect.Parameter.VAR_KEYWORD,
)


class Dependant(DependantProtocol[DependencyType]):
    wire: bool
    autowire: bool

    @overload
    def __init__(
        self,
        call: Optional[AsyncGeneratorProvider[DependencyType]] = None,
        *,
        scope: Optional[Scope] = None,
        share: bool = True,
        wire: bool = True,
        autowire: bool = True,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[CoroutineProvider[DependencyType]] = None,
        *,
        scope: Optional[Scope] = None,
        share: bool = True,
        wire: bool = True,
        autowire: bool = True,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[GeneratorProvider[DependencyType]] = None,
        *,
        scope: Optional[Scope] = None,
        share: bool = True,
        wire: bool = True,
        autowire: bool = True,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[CallableProvider[DependencyType]] = None,
        *,
        scope: Optional[Scope] = None,
        share: bool = True,
        wire: bool = True,
        autowire: bool = True,
    ) -> None:
        ...

    def __init__(
        self,
        call: Optional[DependencyProviderType[DependencyType]] = None,
        *,
        scope: Scope = None,
        share: bool = True,
        wire: bool = True,
        autowire: bool = True,
    ) -> None:
        self.call = call
        self.scope = scope
        self.dependencies: Optional[
            List[DependencyParameter[DependantProtocol[Any]]]
        ] = None
        self.share = share
        self.autowire = autowire
        self.wire = wire

    def __repr__(self) -> str:
        share = "" if self.share is False else ", share=True"
        return f"{self.__class__.__name__}(call={self.call}, scope={self.scope}{share})"

    @join_docstring_from(DependantProtocol[Any].__hash__)
    def __hash__(self) -> int:
        return id(self.call)

    @join_docstring_from(DependantProtocol[Any].__eq__)
    def __eq__(self, o: object) -> bool:
        if type(self) is not type(o):
            return False
        assert isinstance(o, Dependant)
        if self.share is False or o.share is False:
            return False
        return self.call is o.call

    @join_docstring_from(DependantProtocol[Any].get_dependencies)
    def get_dependencies(
        self,
    ) -> List[DependencyParameter[DependantProtocol[Any]]]:
        """For the Dependant implementation, this serves as a cache layer on
        top of gather_dependencies.
        """
        if self.dependencies is None:
            self.dependencies = self.gather_dependencies()
        return self.dependencies

    def gather_parameters(self) -> Dict[str, inspect.Parameter]:
        """Collect parameters that this dependency needs to construct itself.

        Generally, this means introspecting into our own callable (self.call).
        """
        assert self.call is not None, "Cannot gather parameters without a bound call"
        return get_parameters(self.call)

    def register_parameter(
        self: Dependant[T], param: inspect.Parameter
    ) -> Dependant[T]:
        if self.call is None:
            self.call = infer_call_from_annotation(param)
        return self

    def gather_dependencies(
        self,
    ) -> List[DependencyParameter[DependantProtocol[Any]]]:
        """Collect this dependencies sub dependencies.

        The returned dict corresponds to keyword arguments that will be passed
        to this dependencies `call` after all sub-dependencies are themselves resolved.
        """
        if self.wire is False:
            return []
        assert (
            self.call is not None
        ), "Container should have assigned call; this is a bug!"
        res: List[DependencyParameter[DependantProtocol[Any]]] = []
        for param in self.gather_parameters().values():
            if param.kind in _VARIABLE_PARAMETER_KINDS and self.autowire:
                continue
            if isinstance(param.default, Dependant):
                sub_dependant: DependantProtocol[Any] = param.default
            elif param.default is param.empty and self.autowire:
                sub_dependant = self.create_sub_dependant(param)
            else:
                continue  # pragma: no cover
            sub_dependant = sub_dependant.register_parameter(param)
            res.append(DependencyParameter(dependency=sub_dependant, parameter=param))
        return res

    def create_sub_dependant(self, param: inspect.Parameter) -> DependantProtocol[Any]:
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

        It is recommended to transfer `scope` and possibly `share` to sub-dependencies created in this manner.
        """
        if param.annotation is inspect.Parameter.empty:
            raise WiringError(
                "Cannot wire a parameter with no default and no type annotation"
            )
        return Dependant[Any](
            call=param.annotation,
            scope=self.scope,
            share=self.share,
            autowire=self.autowire,
        )


class JoinedDependant(Dependant[DependencyType]):
    """A Dependant that aggregates other dependants without directly depending on them"""

    def __init__(
        self,
        dependant: DependantProtocol[DependencyType],
        *,
        siblings: Iterable[DependantProtocol[Any]],
        scope: Scope = None,
        share: bool = True,
        autowire: bool = True,
    ) -> None:
        self.call = dependant.call
        self.dependant = dependant
        self.siblings = siblings
        self.scope = scope
        self.dependencies: Optional[
            List[DependencyParameter[DependantProtocol[Any]]]
        ] = None
        self.share = share
        self.autowire = autowire

    def gather_dependencies(self) -> List[DependencyParameter[DependantProtocol[Any]]]:
        return [
            *self.dependant.get_dependencies(),
            *(DependencyParameter(dep, None) for dep in self.siblings),
        ]


class UniqueDependant(Dependant[DependencyType]):
    """A Dependant that can be cached/shared but is never substituted with another Dependant in the DAG"""

    # By overriding __eq__, __hash__ gets set to None
    # see https://docs.python.org/3/reference/datamodel.html#object.__hash__ a couple paragraphs down
    def __hash__(self) -> int:
        return super().__hash__()

    def __eq__(self, o: object) -> bool:
        return False


class CallableClass(Protocol[T]):
    __call__: DependencyProviderType[T]


class CallableClassDependant(Dependant[T]):
    """A Dependant that makes it simple to have multiple instances of a callable class that are cached and shared seperateley
    You pass in the class, and you will get the return value of it's __call__.
    Each CallableClassDependant has it's own instance of the class, and you can have multiple instances.
    """

    # Note: this would be a good application of higher kinded types
    # We want to get (1) a function that produces a class C and (B) that class
    # That is, it would be nice to replace CallableClass[T]
    # with something like Cls = TypeVar("Cls", bound=CallableClass[T])
    # And then use call: Type[Cls[T]] and cls_provider: Callable[..., Cls[T]]
    def __init__(
        self,
        call: Type[CallableClass[T]],
        *,
        cls_provider: Optional[DependencyProviderType[CallableClass[Any]]] = None,
        instance_scope: Scope = None,
        scope: Scope = None,
        share: bool = True,
        wire: bool = True,
        autowire: bool = True,
    ) -> None:
        if not (inspect.isclass(call) and hasattr(call, "__call__")):
            raise TypeError("call must be a callable class")
        self._cls_provider = cls_provider or call
        self._instance_scope = instance_scope
        super().__init__(
            call=call.__call__,
            scope=scope,
            share=share,
            wire=wire,
            autowire=autowire,
        )

    def create_sub_dependant(self, param: inspect.Parameter) -> DependantProtocol[Any]:
        if param.name == "self":
            return UniqueDependant(
                self._cls_provider,
                scope=self._instance_scope,
                share=True,
                wire=self.wire,
                autowire=self.autowire,
            )
        return super().create_sub_dependant(param)
