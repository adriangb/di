from typing import Any, Optional

from anydep.models import Dependant, Dependency, DependencyProvider


def Depends(
    call: Optional[DependencyProvider] = None,
    *,
    lifespan_policy: Optional[Any] = None,
    cache_policy: Optional[Any] = None
) -> Dependency:
    return Dependant(  # type: ignore
        call=call,
        lifespan_policy=lifespan_policy,
        cache_policy=cache_policy,
    )
