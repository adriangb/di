import inspect
import sys
from typing import Generator

if sys.version_info < (3, 9):
    from typing_extensions import Annotated, get_args, get_origin
else:
    from typing import Annotated, get_args, get_origin

from di._utils.inspect import get_parameters
from di.api.dependencies import MarkerBase

__all__ = ("get_parameters", "get_markers_from_parameter")


def get_markers_from_parameter(
    param: inspect.Parameter,
) -> Generator[MarkerBase, None, None]:
    """Infer a sub-dependant from a parameter of this Dependant's .call


    In the case of multiple markers in PEP 593 Annotated or nested use of Annotated
    (which are equivalent and get flattened by Annoated itself) we return markers from
    right to left or outer to inner.
    """
    if get_origin(param.annotation) is Annotated:
        # reverse the arguments so that in the case of
        # Annotated[Annotated[T, InnerDependant()], OuterDependant()]
        # we discover "outer" first
        # This is a somewhat arbitrary choice, but it is the convention we'll go with
        # See https://www.python.org/dev/peps/pep-0593/#id18 for more details
        for arg in reversed(get_args(param.annotation)):
            if isinstance(arg, MarkerBase):
                yield arg
