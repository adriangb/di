from __future__ import annotations

import inspect
from typing import Any, Iterable, List, Mapping, Optional, TypeVar, overload

from di._utils.inspect import get_parameters, get_type
from di.api.dependencies import CacheKey, DependantBase, DependencyParameter
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

    @property
    def cache_key(self) -> CacheKey:
        """Used to identify Dependants.
        By default, just checks that both are marked as shared.
        See DependantBase for more details.
        """
        if self.share is False:
            return self
        return (self.call, self.scope)  # type: ignore[return-value]

    def register_parameter(self, param: inspect.Parameter) -> DependantBase[Any]:
        """Hook to register the parameter this Dependant corresponds to.

        This can be used to inferr self.call from a type annotation (autowiring),
        or to just register the type annotation.

        This method can return the same or a new instance of a Dependant to avoid modifying itself.
        """
        if self.wire is False:
            return self
        if self.call is None:
            annotation_type_option = get_type(param)
            if annotation_type_option is not None:
                self.call = annotation_type_option.value
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
                if maybe_sub_dependant is not None:
                    sub_dependant = maybe_sub_dependant
                elif param.default is param.empty:
                    # try to auto-wire
                    sub_dependant = Dependant[Any](
                        call=None,
                        scope=self.scope,
                        share=self.share,
                    )
                else:
                    # has a default parameter but we create a dependency anyway just for binds
                    # but do not wire it to make autowiring less brittle and less magic
                    sub_dependant = Dependant[Any](
                        call=None,
                        scope=self.scope,
                        share=self.share,
                        wire=False,
                    )
            res.append(DependencyParameter(dependency=sub_dependant, parameter=param))
        return res

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(call={self.call}, share={self.share})"


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

    def register_parameter(self, param: inspect.Parameter) -> DependantBase[T]:
        self.dependant = self.dependant.register_parameter(param)
        return self

    @property
    def cache_key(self) -> CacheKey:
        return (self.dependant.cache_key, tuple((s.cache_key for s in self.siblings)))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(dependant={self.dependant}, siblings={self.siblings})"
