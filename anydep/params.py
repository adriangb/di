from typing import Any, Optional, Union, overload

from anydep.models import (
    AsyncCallableClass,
    AsyncGeneratorProvider,
    CallableClassDependant,
    CallableProvider,
    CoroutineProvider,
    Dependant,
    DependencyProviderType,
    DependencyType,
    GeneratorProvider,
    Scope,
    SyncCallableClass,
)


@overload
def Depends(
    call: Optional[AsyncGeneratorProvider[DependencyType]] = None, *, scope: Optional[Scope] = None, **kwargs: Any
) -> DependencyType:
    ...


@overload
def Depends(
    call: Optional[CoroutineProvider[DependencyType]] = None, *, scope: Optional[Scope] = None, **kwargs: Any
) -> DependencyType:
    ...


@overload
def Depends(
    call: Optional[GeneratorProvider[DependencyType]] = None, *, scope: Optional[Scope] = None, **kwargs: Any
) -> DependencyType:
    ...


@overload
def Depends(
    call: Optional[CallableProvider[DependencyType]] = None, *, scope: Optional[Scope] = None, **kwargs: Any
) -> DependencyType:
    ...


def Depends(
    call: Optional[DependencyProviderType[DependencyType]] = None, *, scope: Optional[Scope] = None, **kwargs: Any
) -> DependencyType:
    return Dependant(call=call, scope=scope, **kwargs)  # type: ignore


@overload
def CallableClass(
    cls: AsyncCallableClass[DependencyType], *, scope: Optional[Scope] = None, **kwargs: Any
) -> DependencyType:
    ...


@overload
def CallableClass(
    cls: SyncCallableClass[DependencyType], *, scope: Optional[Scope] = None, **kwargs: Any
) -> DependencyType:
    ...


def CallableClass(
    cls: Union[SyncCallableClass[DependencyType], AsyncCallableClass[DependencyType]],
    *,
    scope: Optional[Scope] = None,
    **kwargs: Any
) -> DependencyType:
    return CallableClassDependant(cls=cls, call=cls.__call__, scope=scope, **kwargs)  # type: ignore
