import inspect
from typing import Any, Optional

from di.api.providers import DependencyProvider
from di.api.scopes import Scope
from di.dependent._dependent import Dependent


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

        def create_dependent(cls_: Any, param: inspect.Parameter) -> Dependent[Any]:
            return Dependent(call or cls_, scope=scope, use_cache=use_cache)

        cls.__di_dependency__ = classmethod(create_dependent)  # type: ignore
