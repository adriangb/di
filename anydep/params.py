from typing import Optional

from anydep.models import Dependant, Dependency, DependencyProviderType, Scope


def Depends(call: Optional[DependencyProviderType] = None, *, scope: Optional[Scope] = None) -> Dependency:
    return Dependant(  # type: ignore
        call=call,
        scope=scope,
    )
