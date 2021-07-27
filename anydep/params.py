from typing import Optional

from anydep.models import Dependant, DependencyProviderType, DependencyType, Scope


def Depends(call: Optional[DependencyProviderType[DependencyType]] = None, *, scope: Optional[Scope] = None) -> DependencyType:
    return Dependant(call=call, scope=scope)  # type: ignore
