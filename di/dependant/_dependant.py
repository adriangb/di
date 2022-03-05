from __future__ import annotations

import inspect
from typing import Any, List, Optional, TypeVar, overload

from di._utils.inspect import get_parameters, get_type
from di.api.dependencies import (
    CacheKey,
    DependantBase,
    DependencyParameter,
    InjectableClassProvider,
)
from di.api.providers import (
    AsyncGeneratorProvider,
    CallableProvider,
    CoroutineProvider,
    DependencyProvider,
    DependencyProviderType,
    GeneratorProvider,
)
from di.api.scopes import Scope
from di.typing import get_markers_from_annotation

_VARIABLE_PARAMETER_KINDS = (
    inspect.Parameter.VAR_POSITIONAL,
    inspect.Parameter.VAR_KEYWORD,
)

T = TypeVar("T")


class Marker:
    call: Optional[DependencyProvider]
    dependency: Optional[Any]
    scope: Scope
    use_cache: bool
    wire: bool
    sync_to_thread: bool

    def __init__(
        self,
        call: Optional[DependencyProviderType[Any]] = None,
        *,
        scope: Scope = None,
        use_cache: bool = True,
        wire: bool = True,
        sync_to_thread: bool = False,
    ) -> None:
        # by default we assume that call and dependency are the same thing
        # but we don't enforce this on subclasses so that they can assign
        # arbitrary meaning to dependency, e.g. a class that implements some API
        # to produce a callable
        self.call = self.dependency = call
        self.scope = scope
        self.use_cache = use_cache
        self.wire = wire
        self.sync_to_thread = sync_to_thread

    def register_parameter(self, param: inspect.Parameter) -> DependantBase[Any]:
        """Hook to register the parameter this Dependant corresponds to.

        This can be used to inferr self.call from a type annotation (autowiring),
        or to just register the type annotation.

        This method can return the same or a new instance of a Dependant to avoid modifying itself.
        """
        if self.wire is False:
            return Dependant[Any](
                call=self.call,
                scope=self.scope,
                use_cache=self.use_cache,
                wire=self.wire,
                sync_to_thread=self.sync_to_thread,
            )
        call = self.call
        if call is None and param.default is not param.empty:

            def inject_default_value() -> Any:
                return param.default

            call = inject_default_value
        if call is None:
            annotation_type_option = get_type(param)
            if annotation_type_option is not None and inspect.isclass(
                annotation_type_option.value
            ):
                if issubclass(annotation_type_option.value, InjectableClassProvider):
                    return annotation_type_option.value.__di_dependency__(param)
                else:
                    # a class type, a callable class instance or a function
                    call = annotation_type_option.value
        return Dependant[Any](
            call=call,
            scope=self.scope,
            use_cache=self.use_cache,
            wire=self.wire,
            sync_to_thread=self.sync_to_thread,
        )


class Dependant(DependantBase[T]):
    call: Optional[DependencyProviderType[T]]
    wire: bool
    sync_to_thread: bool
    scope: Scope
    marker: Optional[Marker]

    @overload
    def __init__(
        self,
        call: Optional[AsyncGeneratorProvider[T]] = ...,
        *,
        marker: Optional[Marker] = ...,
        scope: Scope = ...,
        use_cache: bool = ...,
        wire: bool = ...,
        sync_to_thread: bool = ...,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[CoroutineProvider[T]] = ...,
        *,
        marker: Optional[Marker] = ...,
        scope: Scope = ...,
        use_cache: bool = ...,
        wire: bool = ...,
        sync_to_thread: bool = ...,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[GeneratorProvider[T]] = ...,
        *,
        marker: Optional[Marker] = ...,
        scope: Scope = ...,
        use_cache: bool = ...,
        wire: bool = ...,
        sync_to_thread: bool = ...,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[CallableProvider[T]] = None,
        *,
        marker: Optional[Marker] = ...,
        scope: Scope = ...,
        use_cache: bool = ...,
        wire: bool = ...,
        sync_to_thread: bool = ...,
    ) -> None:
        ...

    def __init__(
        self,
        call: Optional[DependencyProviderType[T]] = None,
        *,
        marker: Optional[Marker] = None,
        scope: Scope = None,
        use_cache: bool = True,
        wire: bool = True,
        sync_to_thread: bool = False,
    ) -> None:
        self.call = call
        self.scope = scope
        self.use_cache = use_cache
        self.wire = wire
        self.sync_to_thread = sync_to_thread
        self.marker = marker

    @property
    def cache_key(self) -> CacheKey:
        if self.use_cache is False or self.call is None:
            return (self.__class__, id(self))
        return (self.__class__, self.call)

    def get_dependencies(self) -> List[DependencyParameter]:
        """Collect all of our sub-dependencies as parameters"""
        if self.wire is False or self.call is None:
            return []
        res: List[DependencyParameter] = []
        for param in get_parameters(self.call).values():
            sub_dependant: DependantBase[Any]
            if param.kind in _VARIABLE_PARAMETER_KINDS:
                continue
            else:
                maybe_sub_dependant_marker = next(
                    get_markers_from_annotation(param.annotation, Marker), None
                )
                if maybe_sub_dependant_marker is not None:
                    sub_dependant = maybe_sub_dependant_marker.register_parameter(param)
                else:
                    sub_dependant = self.get_default_marker().register_parameter(param)
            res.append(DependencyParameter(dependency=sub_dependant, parameter=param))
        return res

    def get_default_marker(self) -> Marker:
        return Marker(scope=self.scope, use_cache=self.use_cache)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(call={self.call}, use_cache={self.use_cache})"
        )
