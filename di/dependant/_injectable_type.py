import inspect
from typing import Any, Optional

from di.api.providers import DependencyProvider
from di.api.scopes import Scope
from di.dependant._dependant import Dependant


class Injectable:
    __slots__ = ()

    def __init_subclass__(
        cls,
        call: Optional[DependencyProvider] = None,
        scope: Scope = None,
        use_cache: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init_subclass__(**kwargs)

        def create_dependant(cls_: Any, param: inspect.Parameter) -> Dependant[Any]:
            return Dependant(call or cls_, scope=scope, use_cache=use_cache)

        cls.__di_dependency__ = classmethod(create_dependant)  # type: ignore
