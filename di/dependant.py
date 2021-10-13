from __future__ import annotations

import inspect
from typing import Any, Dict, List, Optional, overload

from di._docstrings import join_docstring_from
from di._inspect import get_parameters, infer_call_from_annotation
from di.exceptions import WiringError
from di.types.dependencies import DependantProtocol, DependencyParameter
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


class Dependant(DependantProtocol[DependencyType], object):
    wire: bool
    autowire: bool

    @overload
    def __init__(
        self,
        call: Optional[AsyncGeneratorProvider[DependencyType]] = None,
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
        scope: Optional[Scope] = None,
        share: bool = True,
        wire: bool = True,
        autowire: bool = True,
    ) -> None:
        ...

    def __init__(
        self,
        call: Optional[DependencyProviderType[DependencyType]] = None,
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
        assert isinstance(o, type(self))
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
        if self.dependencies is None:  # type: ignore
            self.dependencies = self.gather_dependencies()
        return self.dependencies

    def gather_parameters(self) -> Dict[str, inspect.Parameter]:
        """Collect parameters that this dependency needs to construct itself.

        Generally, this means introspecting into our own callable (self.call).
        """
        assert self.call is not None, "Cannot gather parameters without a bound call"
        return get_parameters(self.call)

    def register_parameter(self, param: inspect.Parameter) -> None:
        if self.call is None:
            self.call = infer_call_from_annotation(param)

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
            if param.kind in _VARIABLE_PARAMETER_KINDS:
                raise WiringError(
                    "Dependencies may not use variable positional or keyword arguments"
                )
            if isinstance(param.default, Dependant):
                sub_dependant: DependantProtocol[Any] = param.default
            elif param.default is param.empty and self.autowire:
                sub_dependant = self.create_sub_dependant(param)
            else:
                continue  # pragma: no cover
            sub_dependant.register_parameter(param)
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
