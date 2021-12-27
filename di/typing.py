import inspect
import sys
from typing import Any, Optional, cast

if sys.version_info < (3, 9):
    from typing_extensions import Annotated, get_args, get_origin
else:
    from typing import Annotated, get_args, get_origin

from di._utils.inspect import get_parameters
from di.api.dependencies import DependantBase

__all__ = ("get_parameters", "get_marker_from_parameter")


def get_marker_from_parameter(param: inspect.Parameter) -> Optional[DependantBase[Any]]:
    """Infer a sub-dependant from a parameter of this Dependant's .call

    By default, we look for Depends(...) markers (which are instances of DependantBase)
    in the default values and PEP 593 typing annotations.
    """
    if isinstance(param.default, DependantBase):
        return cast(DependantBase[Any], param.default)
    if get_origin(param.annotation) is Annotated:
        for arg in get_args(param.annotation):
            if isinstance(arg, DependantBase):
                return cast(DependantBase[Any], arg)
    return None
