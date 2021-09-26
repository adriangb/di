"""Convenience functions, mainly for the purpose of providing proper type annotations for default arguments.
"""

from typing import Optional, overload

from di.dependency import (
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
    call: Optional[AsyncGeneratorProvider[DependencyType]] = None,
    *,
    scope: Optional[Scope] = None,
    shared: bool = True
) -> DependencyType:
    ...


@overload
def Depends(
    call: Optional[CoroutineProvider[DependencyType]] = None,
    *,
    scope: Optional[Scope] = None,
    shared: bool = True
) -> DependencyType:
    ...


@overload
def Depends(
    call: Optional[GeneratorProvider[DependencyType]] = None,
    *,
    scope: Optional[Scope] = None,
    shared: bool = True
) -> DependencyType:
    ...


@overload
def Depends(
    call: Optional[CallableProvider[DependencyType]] = None,
    *,
    scope: Optional[Scope] = None,
    shared: bool = True
) -> DependencyType:
    ...


def Depends(
    call: Optional[DependencyProviderType[DependencyType]] = None,
    *,
    scope: Optional[Scope] = None,
    shared: bool = True
) -> DependencyType:
    return Dependant(call=call, scope=scope, shared=shared)  # type: ignore
