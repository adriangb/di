from __future__ import annotations

import inspect
import sys
from itertools import chain
from typing import Any, Dict, Iterable, List, Mapping, Optional, Type, cast, overload

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

from di._docstrings import join_docstring_from
from di._inspect import get_parameters, infer_call_from_annotation
from di.exceptions import WiringError
from di.types.dependencies import DependantBase, DependencyParameter, T
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


class Dependant(DependantBase[DependencyType]):
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
        overrides: Optional[Mapping[str, DependantBase[Any]]] = None,
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
        overrides: Optional[Mapping[str, DependantBase[Any]]] = None,
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
        overrides: Optional[Mapping[str, DependantBase[Any]]] = None,
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
        overrides: Optional[Mapping[str, DependantBase[Any]]] = None,
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
        overrides: Optional[Mapping[str, DependantBase[Any]]] = None,
    ) -> None:
        self.call = call
        self.scope = scope
        self.dependencies: Optional[
            List[DependencyParameter[DependantBase[Any]]]
        ] = None
        self.share = share
        self.autowire = autowire
        self.wire = wire
        self.overrides = overrides or {}

    @join_docstring_from(DependantBase[Any].__hash__)
    def __hash__(self) -> int:
        return id(self.call)

    @join_docstring_from(DependantBase[Any].__eq__)
    def __eq__(self, o: object) -> bool:
        if type(self) != type(o):
            return False
        o = cast(Dependant[Any], o)
        if self.share is False or o.share is False:
            return False
        return self.call is o.call

    @join_docstring_from(DependantBase[Any].get_dependencies)
    def get_dependencies(
        self,
    ) -> List[DependencyParameter[DependantBase[Any]]]:
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
    ) -> List[DependencyParameter[DependantBase[Any]]]:
        """Collect this dependencies sub dependencies.

        The returned dict corresponds to keyword arguments that will be passed
        to this dependencies `call` after all sub-dependencies are themselves resolved.
        """
        if self.wire is False:
            return []
        assert (
            self.call is not None
        ), "Container should have assigned call; this is a bug!"
        res: List[DependencyParameter[DependantBase[Any]]] = []
        for param in self.gather_parameters().values():
            sub_dependant: DependantBase[Any]
            if param.name in self.overrides:
                sub_dependant = self.overrides[param.name]
            elif param.kind in _VARIABLE_PARAMETER_KINDS and self.autowire:
                continue
            elif isinstance(param.default, Dependant):
                sub_dependant = param.default
            elif param.default is param.empty and self.autowire:
                sub_dependant = self.create_sub_dependant(param)
            else:
                continue  # pragma: no cover
            sub_dependant = sub_dependant.register_parameter(param)
            res.append(DependencyParameter(dependency=sub_dependant, parameter=param))
        return res

    def create_sub_dependant(self, param: inspect.Parameter) -> DependantBase[Any]:
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


class JoinedDependant(DependantBase[DependencyType]):
    """A Dependant that aggregates other dependants without directly depending on them"""

    _dependencies: Optional[List[DependencyParameter[Any]]]

    def __init__(
        self,
        dependant: DependantBase[DependencyType],
        *,
        siblings: Iterable[DependantBase[Any]],
    ) -> None:
        self.call = dependant.call
        self.dependant = dependant
        self.siblings = siblings
        self.scope = dependant.scope
        self._dependencies = None
        self.share = dependant.share

    def get_dependencies(self) -> List[DependencyParameter[DependantBase[Any]]]:
        if self._dependencies is None:
            self._dependencies = list(
                chain(
                    self.dependant.get_dependencies(),
                    (DependencyParameter(dep, None) for dep in self.siblings),
                )
            )
        return self._dependencies

    def __hash__(self) -> int:
        return hash((self.dependant, *self.siblings))

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, JoinedDependant):
            return False
        return (self.dependant, *self.siblings) == (o.dependant, *o.siblings)

    def register_parameter(
        self, param: inspect.Parameter
    ) -> DependantBase[DependencyType]:
        return self.dependant.register_parameter(param)


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


def CallableClassDependant(
    call: Type[CallableClass[T]],
    *,
    cls_provider: Optional[DependencyProviderType[CallableClass[Any]]] = None,
    instance_scope: Scope = None,
    scope: Scope = None,
    share: bool = True,
    wire: bool = True,
    autowire: bool = True,
) -> Dependant[T]:
    if not (inspect.isclass(call) and hasattr(call, "__call__")):
        raise TypeError("call must be a callable class")
    cls_provider = cls_provider or call
    self = UniqueDependant(
        cls_provider,
        scope=instance_scope,
        share=True,
        wire=wire,
        autowire=autowire,
    )
    return Dependant(
        call=call.__call__,
        scope=scope,
        share=share,
        wire=wire,
        autowire=autowire,
        overrides={"self": self},
    )
