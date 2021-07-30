from inspect import Parameter

import anyio
from fastapi import Request
from pydantic import BaseModel

from anydep.container import Container
from anydep.models import Dependant

# FastAPI code
# This demonstrates (in a very rudimentary way) how FastAPI
# might plug into the DI system to provide path, query, body, headers, etc.


def extract_query(param_name: str, cls):
    def extract(request: Request):
        return cls(request.query_params[param_name])  # or using pydantic somehow

    return extract


def parse_body(model: BaseModel):
    async def parse(request: Request):
        body = await request.body()
        return model.parse_raw(body)

    return parse


# Custom subclasses of Dependant can be used to customize
# gathernig of parameters, inference of injection callable, etc.
# the API can be almost anything, current methods are just first stab


class EndpointDependant(Dependant):
    def infer_call_from_annotation(self, param: Parameter):
        if param.annotation in (int, str, float):  # or more complex evaluation
            # query parameter
            return extract_query(param.name, param.annotation)
        if issubclass(param.annotation, BaseModel):
            # body parameter
            return parse_body(param.annotation)
        return super().infer_call_from_annotation(param)


class HeaderDep(Dependant):
    def infer_call_from_annotation(self, param: Parameter):
        def extract(request: Request = Dependant()):
            return request.headers[param.name]

        return extract


def Header() -> str:
    return HeaderDep()  # type: ignore


# Pseudo-user code
class Item(BaseModel):
    name: str
    price: float


called = False


async def endpoint(query1: int, query2: str, body1: Item, accept: str = Header()):
    global called
    assert query1 == 1234
    assert query2 == "1234"
    assert body1.name == "hammer"
    assert body1.price == 12.42
    assert accept == "application/json"
    called = True


# Test code
async def main():
    container = Container()
    dependant = EndpointDependant(call=endpoint)
    async with container.enter_global_scope("app"):
        async with container.enter_local_scope("request"):
            json_body = '{"name":"hammer","price": 12.42}'.encode()
            request = Request(
                scope={
                    "type": "http",
                    "query_string": "query1=1234&query2=1234",
                    "headers": [(b"accept", b"application/json")],
                }
            )
            request._body = json_body
            container.bind(Request, lambda: request)
            await container.execute(dependant)
    assert called


anyio.run(main)
