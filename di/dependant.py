from __future__ import annotations

import inspect
import sys
from typing import Any, Iterable, List, Mapping, Optional, Type, TypeVar, cast, overload

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

if sys.version_info < (3, 9):
    from typing_extensions import Annotated, get_args, get_origin
else:
    from typing import Annotated, get_args, get_origin

from di._utils.inspect import get_parameters, infer_call_from_annotation
from di.api.dependencies import DependantBase, DependencyParameter
from di.api.providers import (
    AsyncGeneratorProvider,
    CallableProvider,
    CoroutineProvider,
    DependencyProviderType,
    GeneratorProvider,
)
from di.api.scopes import Scope
from di.typing import get_markers_from_parameter

_VARIABLE_PARAMETER_KINDS = (
    inspect.Parameter.VAR_POSITIONAL,
    inspect.Parameter.VAR_KEYWORD,
)

T = TypeVar("T")


class Dependant(DependantBase[T]):
    __slots__ = ("wire", "sync_to_thread", "overrides")

    @overload
    def __init__(
        self,
        call: Optional[AsyncGeneratorProvider[T]] = None,
        *,
        scope: Optional[Scope] = None,
        share: bool = True,
        wire: bool = True,
        overrides: Optional[Mapping[str, DependantBase[Any]]] = None,
        sync_to_thread: bool = False,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[CoroutineProvider[T]] = None,
        *,
        scope: Optional[Scope] = None,
        share: bool = True,
        wire: bool = True,
        overrides: Optional[Mapping[str, DependantBase[Any]]] = None,
        sync_to_thread: bool = False,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[GeneratorProvider[T]] = None,
        *,
        scope: Optional[Scope] = None,
        share: bool = True,
        wire: bool = True,
        overrides: Optional[Mapping[str, DependantBase[Any]]] = None,
        sync_to_thread: bool = False,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[CallableProvider[T]] = None,
        *,
        scope: Optional[Scope] = None,
        share: bool = True,
        wire: bool = True,
        overrides: Optional[Mapping[str, DependantBase[Any]]] = None,
        sync_to_thread: bool = False,
    ) -> None:
        ...

    def __init__(
        self,
        call: Optional[DependencyProviderType[T]] = None,
        *,
        scope: Scope = None,
        share: bool = True,
        wire: bool = True,
        overrides: Optional[Mapping[str, DependantBase[Any]]] = None,
        sync_to_thread: bool = False,
    ) -> None:
        self.call = call
        self.scope = scope
        self.share = share
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
        o = cast(Dependant[T], o)
        if self.share is False or o.share is False:
            return False
        return self.call is o.call and self.overrides == o.overrides

    def register_parameter(
        self: DependantBase[T], param: inspect.Parameter
    ) -> DependantBase[T]:
        """Hook to register the parameter this Dependant corresponds to.

        This can be used to inferr self.call from a type annotation (autowiring),
        or to just register the type annotation.

        This method can return the same or a new instance of a Dependant to avoid modifying itself.
        """
        if self.call is None:
            if get_origin(param.annotation) is Annotated:
                param = param.replace(annotation=next(iter(get_args(param.annotation))))
            if param.annotation is not param.empty:
                self.call = infer_call_from_annotation(param)
        return self

    def get_dependencies(self) -> List[DependencyParameter]:
        """Collect all of our sub-dependencies as parameters"""
        if self.wire is False or self.call is None:
            return []
        res: List[DependencyParameter] = []
        for param in get_parameters(self.call).values():
            sub_dependant: DependantBase[Any]
            if param.name in self.overrides:
                sub_dependant = self.overrides[param.name]
            elif param.kind in _VARIABLE_PARAMETER_KINDS:
                continue
            else:
                maybe_sub_dependant = next(get_markers_from_parameter(param), None)
                if maybe_sub_dependant is None:
                    sub_dependant = self.create_sub_dependant(param)
                else:
                    sub_dependant = maybe_sub_dependant
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
        >>> def parent(foo: Annotated[..., Depends(foo_factory)]):
        >>>    ...

        In this scenario, `Depends(foo_factory)` will call
        `Depends(foo_factory).create_sub_dependant(Parameter(Foo))`.

        Usually you'll transfer `scope` and possibly `share`
        to sub-dependencies created in this manner.
        """
        return Dependant[Any](
            call=None,
            scope=self.scope,
            share=self.share,
        )


class JoinedDependant(DependantBase[T]):
    """A Dependant that aggregates other dependants without directly depending on them"""

    __slots__ = ("dependant", "siblings")

    def __init__(
        self,
        dependant: DependantBase[T],
        *,
        siblings: Iterable[DependantBase[Any]],
    ) -> None:
        self.call = dependant.call
        self.dependant = dependant
        self.siblings = siblings
        self.scope = dependant.scope
        self.share = dependant.share

    def get_dependencies(self) -> List[DependencyParameter]:
        """Get the dependencies of our main dependant and all siblings"""
        return [
            *self.dependant.get_dependencies(),
            *(DependencyParameter(dep, None) for dep in self.siblings),
        ]

    def __hash__(self) -> int:
        return hash((self.dependant, *self.siblings))

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, JoinedDependant):
            return False
        return (self.dependant, *self.siblings) == (o.dependant, *o.siblings)

    def register_parameter(self, param: inspect.Parameter) -> DependantBase[T]:
        self.dependant = self.dependant.register_parameter(param)
        return self


class CallableClass(Protocol[T]):
    """A callable class that has a __call__ that is valid as dependency provider"""

    __call__: DependencyProviderType[T]


def CallableClassDependant(
    call: Type[CallableClass[T]],
    *,
    instance_scope: Scope = None,
    scope: Scope = None,
    share: bool = True,
    wire: bool = True,
) -> Dependant[T]:
    """Create a Dependant that will create and call a callable class

    The class instance can come from the class' constructor (by default)
    or be provided by cls_provider.
    """
    if not (inspect.isclass(call) and hasattr(call, "__call__")):
        raise TypeError("call must be a callable class")
    instance = Dependant[CallableClass[T]](
        call,
        scope=instance_scope,
        share=True,
        wire=wire,
    )
    return Dependant[T](
        call=call.__call__,
        scope=scope,
        share=share,
        wire=wire,
        overrides={"self": instance},
    )
