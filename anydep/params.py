"""Convenience functions, mainly for the purpose of providing proper type annotations for default arguments.
"""

from typing import Optional, overload

from anydep.dependency import (
    AsyncGeneratorProvider,
    CallableProvider,
    CoroutineProvider,
    Dependant,
    Dependency,
    DependencyProvider,
    DependencyType,
    GeneratorProvider,
    Scope,
)


@overload
def Depends(
    call: Optional[AsyncGeneratorProvider[DependencyType]] = None,
    *,
    scope: Optional[Scope] = None
) -> DependencyType:
    ...


@overload
def Depends(
    call: Optional[CoroutineProvider[DependencyType]] = None,
    *,
    scope: Optional[Scope] = None
) -> DependencyType:
    ...


@overload
def Depends(
    call: Optional[GeneratorProvider[DependencyType]] = None,
    *,
    scope: Optional[Scope] = None
) -> DependencyType:
    ...


@overload
def Depends(
    call: Optional[CallableProvider[DependencyType]] = None,
    *,
    scope: Optional[Scope] = None
) -> DependencyType:
    ...


def Depends(
    call: Optional[DependencyProvider] = None, *, scope: Optional[Scope] = None
) -> Dependency:
    return Dependant(call=call, scope=scope)  # type: ignore
