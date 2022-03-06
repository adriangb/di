import inspect
from typing import Any, Optional

from di._utils.inspect import get_type
from di.api.dependencies import DependantBase
from di.container._bind_hook import BindHook


def bind_by_type(
    provider: DependantBase[Any],
    dependency: type,
    *,
    covariant: bool = False,
) -> BindHook:
    def hook(
        param: Optional[inspect.Parameter], dependant: DependantBase[Any]
    ) -> Optional[DependantBase[Any]]:
        if dependant.call is dependency:
            return provider
        if param is None:
            return None
        type_annotation_option = get_type(param)
        if type_annotation_option is None:
            return None
        type_annotation = type_annotation_option.value
        if type_annotation is dependency:
            return provider
        if covariant:
            if inspect.isclass(type_annotation) and inspect.isclass(dependency):
                if dependency in type_annotation.__mro__:
                    return provider
        return None

    return hook
