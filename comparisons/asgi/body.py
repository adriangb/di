import functools
import json
import typing
from dataclasses import is_dataclass

from dacite import from_dict  # type: ignore
from pydantic import BaseModel
from starlette.requests import Request

from anydep.models import Dependant, DependencyProvider, Parameter
from anydep.params import Depends

T = typing.TypeVar("T")


class BodyDependant(Dependant):
    def __init__(self, default: typing.Any) -> None:
        self.default = default
        super().__init__(call=None)

    @staticmethod
    def get_deserializer(target_cls: typing.Type[T]) -> typing.Callable[[str], T]:
        if is_dataclass(target_cls):
            return lambda json_data: from_dict(target_cls, json.loads(json_data))
        if issubclass(target_cls, BaseModel):
            model = typing.cast(BaseModel, target_cls)
            # parse_raw just has extra optional arguments
            return model.parse_raw  # type: ignore
        raise NotImplementedError

    @functools.lru_cache(maxsize=1)
    def infer_call_from_annotation(self, param: Parameter) -> DependencyProvider:
        # here we define how to build param.annotation from the request

        async def get_body(request: Request = Depends()):
            body = await request.body()
            if not body:
                if self.default is ...:
                    raise TypeError
                return self.default
            return self.get_deserializer(param.annotation)(body.decode())

        return get_body


def Body(default: typing.Any = ...) -> typing.Any:
    return BodyDependant(default=default)
