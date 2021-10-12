"""Convenience functions, mainly for the purpose of providing proper type annotations for default arguments.
"""

from typing import Optional, overload

from di.dependant import Dependant
from di.types.providers import (
    AsyncGeneratorProvider,
    CallableProvider,
    CoroutineProvider,
    DependencyProviderType,
    DependencyType,
    GeneratorProvider,
)
from di.types.scopes import Scope


@overload
def Depends(
    call: Optional[AsyncGeneratorProvider[DependencyType]] = None,
    *,
    scope: Scope = None,
    share: bool = True,
    wire: bool = True,
    autowire: bool = True,
) -> DependencyType:
    ...


@overload
def Depends(
    call: Optional[CoroutineProvider[DependencyType]] = None,
    *,
    scope: Scope = None,
    share: bool = True,
    wire: bool = True,
    autowire: bool = True,
) -> DependencyType:
    ...


@overload
def Depends(
    call: Optional[GeneratorProvider[DependencyType]] = None,
    *,
    scope: Scope = None,
    share: bool = True,
    wire: bool = True,
    autowire: bool = True,
) -> DependencyType:
    ...


@overload
def Depends(
    call: Optional[CallableProvider[DependencyType]] = None,
    *,
    scope: Scope = None,
    share: bool = True,
    wire: bool = True,
    autowire: bool = True,
) -> DependencyType:
    ...


def Depends(
    call: Optional[DependencyProviderType[DependencyType]] = None,
    *,
    scope: Scope = None,
    share: bool = True,
    wire: bool = True,
    autowire: bool = True,
) -> DependencyType:
    return Dependant(call=call, scope=scope, share=share, wire=wire, autowire=autowire)  # type: ignore
