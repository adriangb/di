import functools
import typing

from starlette.requests import Request

from anydep.models import Dependant, DependencyProvider, Parameter
from anydep.params import Depends

T = typing.TypeVar("T")


class HeaderDependant(Dependant):
    def __init__(self, default: typing.Any) -> None:
        self.default = default
        super().__init__(call=None)

    @functools.lru_cache(maxsize=1)
    def infer_call_from_annotation(self, param: Parameter) -> DependencyProvider:
        def get_headers(request: Request = Depends()) -> typing.Any:
            return param.annotation(request.headers.get(param.name.replace("_", "-"), self.default))

        return get_headers


def Header(default: typing.Any = ...) -> typing.Any:
    return HeaderDependant(default=default)
