from __future__ import annotations

import inspect
import sys
from itertools import chain
from typing import Any, Dict, Iterable, List, Mapping, Optional, Type, cast, overload

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

if sys.version_info < (3, 9):
    from typing_extensions import Annotated, get_args, get_origin
else:
    from typing import Annotated, get_args, get_origin

from di._utils.inspect import get_parameters, infer_call_from_annotation
from di.api.dependencies import DependantBase, DependencyParameter, T
from di.api.providers import (
    AsyncGeneratorProvider,
    CallableProvider,
    CoroutineProvider,
    DependencyProvider,
    DependencyProviderType,
    DependencyType,
    GeneratorProvider,
)
from di.api.scopes import Scope
from di.exceptions import WiringError

_VARIABLE_PARAMETER_KINDS = (
    inspect.Parameter.VAR_POSITIONAL,
    inspect.Parameter.VAR_KEYWORD,
)


class Dependant(DependantBase[DependencyType]):
    wire: bool
    autowire: bool
    sync_to_thread: bool
    __slots__ = ("wire", "autowire", "sync_to_thread", "dependencies", "overrides")

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
        sync_to_thread: bool = False,
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
        sync_to_thread: bool = False,
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
        sync_to_thread: bool = False,
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
        sync_to_thread: bool = False,
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
        sync_to_thread: bool = False,
    ) -> None:
        self.call = call
        self.scope = scope
        self.dependencies: Optional[List[DependencyParameter]] = None
        self.share = share
        self.autowire = autowire
        self.wire = wire
        self.overrides = overrides or {}
        self.sync_to_thread = sync_to_thread

    def __hash__(self) -> int:
        """Used to identify Dependants.
        By default, we identify Dependant's by their callable.
        See DependantBase for more details.
        """
        return id(self.call)

    def __eq__(self, o: object) -> bool:
        """Used to identify Dependants.
        By default, just checks that both are marked as shared.
        See DependantBase for more details.
        """
        if type(self) != type(o):
            return False
        o = cast(Dependant[Any], o)
        if self.share is False or o.share is False:
            return False
        return self.call is o.call

    def get_dependencies(
        self,
    ) -> List[DependencyParameter]:
        """Collect all of the sub dependencies for this dependant

        For the Dependant implementation, this serves as a cache layer on
        top of gather_dependencies.
        """
        if self.dependencies is None:
            self.dependencies = self.gather_dependencies()
        return self.dependencies

    @staticmethod
    def gather_parameters(call: DependencyProvider) -> Dict[str, inspect.Parameter]:
        """Collect parameters that this dependency needs to construct itself.

        Generally, this means introspecting into our own callable (self.call).
        """
        return get_parameters(call)

    def register_parameter(
        self: Dependant[T], param: inspect.Parameter
    ) -> Dependant[T]:
        """Called by the parent so that us / this / the child can register the parameter it is attached to."""
        if self.call is None:
            if get_origin(param.annotation) is Annotated:
                param = param.replace(annotation=next(iter(get_args(param.annotation))))
            if param.annotation is not param.empty:
                self.call = infer_call_from_annotation(param)
        return self

    @staticmethod
    def get_sub_dependant_from_paramter(
        param: inspect.Parameter,
    ) -> Optional[DependantBase[Any]]:
        """Infer a sub-dependant from a parameter of this Dependant's .call

        By default, we look for Depends(...) markers (which are instances of DependantBase)
        in the default values and PEP 593 typing annotations.
        """
        if isinstance(param.default, DependantBase):
            return param.default
        if get_origin(param.annotation) is Annotated:
            for arg in get_args(param.annotation):
                if isinstance(arg, DependantBase):
                    return arg
        return None

    def gather_dependencies(
        self,
    ) -> List[DependencyParameter]:
        """Collect this dependencies sub dependencies.

        The returned dict corresponds to keyword arguments that will be passed
        to this dependencies `call` after all sub-dependencies are themselves resolved.
        """
        if self.wire is False:
            return []
        res: List[DependencyParameter] = []
        if self.call is None:
            return res
        for param in self.gather_parameters(self.call).values():
            sub_dependant: DependantBase[Any]
            if param.name in self.overrides:
                sub_dependant = self.overrides[param.name]
            elif param.kind in _VARIABLE_PARAMETER_KINDS and self.autowire:
                continue
            else:
                maybe_sub_dependant = self.get_sub_dependant_from_paramter(param)
                if maybe_sub_dependant is None:
                    if param.default is param.empty and self.autowire:
                        sub_dependant = self.create_sub_dependant(param)
                    else:
                        # use the default value or fail at runtime
                        continue  # pragma: no cover
                else:
                    sub_dependant = maybe_sub_dependant
            param = param.replace(annotation=param.annotation)
            sub_dependant = sub_dependant.register_parameter(param)
            if param.default is param.empty and sub_dependant.call is None:
                raise WiringError(
                    f"The parameter {param.name} to {self.call} has no dependency marker, no type annotation and no default value."
                    " This will produce a TypeError when this function is called."
                    " You must either provide a dependency marker, a type annotation or a default value."
                )
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
        >>> def parent(foo: Depends(foo_factory)):
        >>>    ...

        In this scenario, `Depends(foo_factory)` will call `Depends(foo_factory).create_sub_dependant(Foo)`.

        Usually you'll transfer `scope` and possibly `share` to sub-dependencies created in this manner.
        """
        return Dependant[Any](
            call=None,
            scope=self.scope,
            share=self.share,
            autowire=self.autowire,
        )


class JoinedDependant(DependantBase[DependencyType]):
    """A Dependant that aggregates other dependants without directly depending on them"""

    __slots__ = ("dependant", "siblings", "_dependencies")

    _dependencies: Optional[List[DependencyParameter]]

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

    def get_dependencies(self) -> List[DependencyParameter]:
        """Get the dependencies of our main dependant and all siblings"""
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
        self.dependant = self.dependant.register_parameter(param)
        return self


class UniqueDependant(Dependant[DependencyType]):
    """A Dependant that can be cached/shared but is never substituted with another Dependant in the DAG"""

    # By overriding __eq__, __hash__ gets set to None
    # see https://docs.python.org/3/reference/datamodel.html#object.__hash__ a couple paragraphs down
    def __hash__(self) -> int:
        return super().__hash__()

    def __eq__(self, o: object) -> bool:
        return o is self


class CallableClass(Protocol[T]):
    """A callable class that has a __call__ that is valid as dependency provider"""

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
    """Create a Dependant that will create and call a callable class

    The class instance can come from the class' constructor (by default)
    or be provided by cls_provider.
    """
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
    return Dependant[T](
        call=call.__call__,
        scope=scope,
        share=share,
        wire=wire,
        autowire=autowire,
        overrides={"self": self},
    )
