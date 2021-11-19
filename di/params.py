"""Convenience functions, mainly for the purpose of providing proper type annotations for default arguments.
"""

from typing import Optional, overload

from di.api.providers import (
    AsyncGeneratorProvider,
    CallableProvider,
    CoroutineProvider,
    DependencyProviderType,
    DependencyType,
    GeneratorProvider,
)
from di.api.scopes import Scope
from di.dependant import Dependant


@overload
def Depends(
    call: Optional[AsyncGeneratorProvider[DependencyType]] = None,
    *,
    scope: Scope = None,
    share: bool = True,
    wire: bool = True,
    autowire: bool = True,
    sync_to_thread: bool = False,
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
    sync_to_thread: bool = False,
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
    sync_to_thread: bool = False,
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
    sync_to_thread: bool = False,
) -> DependencyType:
    ...


def Depends(
    call: Optional[DependencyProviderType[DependencyType]] = None,
    *,
    scope: Scope = None,
    share: bool = True,
    wire: bool = True,
    autowire: bool = True,
    sync_to_thread: bool = False,
) -> DependencyType:
    return Dependant(  # type: ignore[return-value]
        call=call,
        scope=scope,
        share=share,
        wire=wire,
        autowire=autowire,
        sync_to_thread=sync_to_thread,
    )
