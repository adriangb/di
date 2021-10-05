from __future__ import annotations

import inspect
from typing import Any, Dict, Optional, overload

from di._docstrings import join_docstring_from
from di._inspect import get_parameters, infer_call_from_annotation
from di.exceptions import WiringError
from di.types.dependencies import DependantProtocol, DependencyParameter
from di.types.providers import (
    AsyncGeneratorProvider,
    CallableProvider,
    CoroutineProvider,
    DependencyProvider,
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
    @overload
    def __init__(
        self,
        call: Optional[AsyncGeneratorProvider[DependencyType]] = None,
        scope: Optional[Scope] = None,
        share: bool = True,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[CoroutineProvider[DependencyType]] = None,
        scope: Optional[Scope] = None,
        share: bool = True,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[GeneratorProvider[DependencyType]] = None,
        scope: Optional[Scope] = None,
        share: bool = True,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[CallableProvider[DependencyType]] = None,
        scope: Optional[Scope] = None,
        share: bool = True,
    ) -> None:
        ...

    def __init__(
        self,
        call: Optional[DependencyProviderType[DependencyType]] = None,
        scope: Scope = None,
        share: bool = True,
    ) -> None:
        self.call = call
        self.scope = scope
        self.dependencies: Optional[
            Dict[str, DependencyParameter[DependantProtocol[Any]]]
        ] = None
        self.share = share

    def __repr__(self) -> str:
        share = "" if self.share is False else ", share=False"
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
    ) -> Dict[str, DependencyParameter[DependantProtocol[Any]]]:
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
            call = infer_call_from_annotation(param)
            if call is inspect.Parameter.empty:
                raise WiringError(
                    "Cannot wire a parameter with no default and no type annotation"
                )
            self.call = call

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
            if isinstance(param.default, Dependant):
                sub_dependant: DependantProtocol[Any] = param.default
            elif param.default is param.empty:
                sub_dependant = self.create_sub_dependant(
                    call=None,
                    scope=self.scope,
                    share=self.share,
                )
            else:
                continue  # pragma: no cover
            sub_dependant.register_parameter(param)
            res[param_name] = DependencyParameter(
                dependency=sub_dependant, parameter=param
            )
        return res

    def create_sub_dependant(
        self, call: Optional[DependencyProvider], scope: Scope, share: bool
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

        It is recommended to transfer `scope` and possibly `share` to sub-dependencies created in this manner.
        """
        return Dependant[Any](call=call, scope=scope, share=share)
