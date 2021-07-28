from typing import Optional, overload

from anydep.models import (
    AsyncGeneratorProvider,
    CallableProvider,
    CoroutineProvider,
    Dependant,
    DependencyProviderType,
    DependencyType,
    GeneratorProvider,
    Scope,
)


@overload
def Depends(
    call: Optional[AsyncGeneratorProvider[DependencyType]] = None, *, scope: Optional[Scope] = None
) -> DependencyType:
    ...


@overload
def Depends(
    call: Optional[CoroutineProvider[DependencyType]] = None, *, scope: Optional[Scope] = None
) -> DependencyType:
    ...


@overload
def Depends(
    call: Optional[GeneratorProvider[DependencyType]] = None, *, scope: Optional[Scope] = None
) -> DependencyType:
    ...


@overload
def Depends(
    call: Optional[CallableProvider[DependencyType]] = None, *, scope: Optional[Scope] = None
) -> DependencyType:
    ...


def Depends(
    call: Optional[DependencyProviderType[DependencyType]] = None, *, scope: Optional[Scope] = None
) -> DependencyType:
    return Dependant(call=call, scope=scope)  # type: ignore
