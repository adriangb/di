from __future__ import annotations

import inspect
from typing import Any, Iterable, List, Optional, TypeVar, overload

from di._utils.inspect import get_parameters, get_type
from di.api.dependencies import CacheKey, DependantBase, DependencyParameter, MarkerBase
from di.api.providers import (
    AsyncGeneratorProvider,
    CallableProvider,
    CoroutineProvider,
    DependencyProvider,
    DependencyProviderType,
    GeneratorProvider,
    InjectableClassProvider,
)
from di.api.scopes import Scope
from di.typing import get_markers_from_parameter

_VARIABLE_PARAMETER_KINDS = (
    inspect.Parameter.VAR_POSITIONAL,
    inspect.Parameter.VAR_KEYWORD,
)

T = TypeVar("T")


class Marker(MarkerBase):
    call: Optional[DependencyProvider]
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
        self.call = call
        self.scope = scope
        self.use_cache = use_cache
        self.wire = wire
        self.sync_to_thread = sync_to_thread

    def from_callable(
        self, call: Optional[DependencyProviderType[Any]]
    ) -> DependantBase[Any]:
        return Dependant[Any](
            call=call,
            scope=self.scope,
            use_cache=self.use_cache,
            wire=self.wire,
            sync_to_thread=self.sync_to_thread,
        )

    def register_parameter(self, param: inspect.Parameter) -> DependantBase[Any]:
        """Hook to register the parameter this Dependant corresponds to.

        This can be used to inferr self.call from a type annotation (autowiring),
        or to just register the type annotation.

        This method can return the same or a new instance of a Dependant to avoid modifying itself.
        """
        if self.wire is False:
            return self.from_callable(self.call)
        call = self.call
        if call is None:
            annotation_type_option = get_type(param)
            if annotation_type_option is not None:
                if isinstance(annotation_type_option.value, InjectableClassProvider):
                    return annotation_type_option.value.__di_dependency__().register_parameter(
                        param
                    )
                else:
                    # a class type, a callable class instance or a function
                    call = annotation_type_option.value
        return self.from_callable(call)


class Dependant(DependantBase[T]):
    wire: bool
    sync_to_thread: bool

    @overload
    def __init__(
        self,
        call: Optional[AsyncGeneratorProvider[T]] = None,
        *,
        scope: Scope = None,
        use_cache: bool = True,
        wire: bool = True,
        sync_to_thread: bool = False,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[CoroutineProvider[T]] = None,
        *,
        scope: Scope = None,
        use_cache: bool = True,
        wire: bool = True,
        sync_to_thread: bool = False,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[GeneratorProvider[T]] = None,
        *,
        scope: Scope = None,
        use_cache: bool = True,
        wire: bool = True,
        sync_to_thread: bool = False,
    ) -> None:
        ...

    @overload
    def __init__(
        self,
        call: Optional[CallableProvider[T]] = None,
        *,
        scope: Scope = None,
        use_cache: bool = True,
        wire: bool = True,
        sync_to_thread: bool = False,
    ) -> None:
        ...

    def __init__(
        self,
        call: Optional[DependencyProviderType[T]] = None,
        *,
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
                    get_markers_from_parameter(param), None
                )
                if maybe_sub_dependant_marker is not None:
                    sub_dependant = maybe_sub_dependant_marker.register_parameter(param)
                else:
                    sub_dependant = self.initialize_sub_dependant(param)
            res.append(DependencyParameter(dependency=sub_dependant, parameter=param))
        return res

    def initialize_sub_dependant(self, param: inspect.Parameter) -> DependantBase[Any]:
        if param.default is param.empty:
            # try to auto-wire
            return Marker(
                call=None,
                scope=self.scope,
                use_cache=self.use_cache,
            ).register_parameter(param)
        # has a default parameter but we create a dependency anyway just for binds
        # but do not wire it to make autowiring less brittle and less magic
        return Marker(
            call=None,
            scope=self.scope,
            use_cache=self.use_cache,
            wire=False,
        ).register_parameter(param)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(call={self.call}, use_cache={self.use_cache})"
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
        self.use_cache = dependant.use_cache

    def get_dependencies(self) -> List[DependencyParameter]:
        """Get the dependencies of our main dependant and all siblings"""
        return [
            *self.dependant.get_dependencies(),
            *(DependencyParameter(dep, None) for dep in self.siblings),
        ]

    @property
    def cache_key(self) -> CacheKey:
        return (self.dependant.cache_key, tuple((s.cache_key for s in self.siblings)))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(dependant={self.dependant}, siblings={self.siblings})"


class InjectableClass:
    __slots__ = ()

    def __init_subclass__(
        cls,
        call: Optional[DependencyProvider] = None,
        scope: Scope = None,
        use_cache: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init_subclass__(**kwargs)

        def create_marker(cls_: Any) -> Marker:
            return Marker(call or cls_, scope=scope, use_cache=use_cache)

        cls.__di_dependency__ = classmethod(create_marker)  # type: ignore
