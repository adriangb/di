"""A quick example of how DI might be applied to an ASGI framework"""

import json
import typing
from dataclasses import dataclass

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from anydep.container import Container
from anydep.models import Dependant, DependencyProvider, Parameter
from anydep.params import Depends


# Define some DI infrastructure that is ASGI app specific
class BodyDependant(Dependant):
    def __init__(self, default: typing.Any) -> None:
        self.default = default
        super().__init__(call=None)

    def infer_call_from_annotation(self, param: Parameter) -> DependencyProvider:
        # here we define how to build param.annotation from the request
        # this could be extended to query params or headers
        # also this is super haphazard and doesn't deal with nested dataclasses,
        # or sub-dependants
        async def get_body(request: Request = Depends()):
            body = await request.body()
            if not body:
                if self.default is ...:
                    raise TypeError
                return self.default
            return param.annotation(**json.loads(body.decode()))

        return get_body


def Body(default: typing.Any = ...) -> typing.Any:
    return BodyDependant(default=default)


def wrap_endpoint(endpoint: typing.Callable) -> typing.Callable:
    """Get the container from the request object and bind that,
    then repalce the endpoint call with a wired DI execution
    """

    async def wrapped_endpoint(request: Request):
        container: Container = request.state.container
        async with container.enter_local_scope("request"):
            container.bind(Request, lambda: request)
            return await container.execute(Dependant(endpoint))

    return wrapped_endpoint


class DIRoute(Route):
    """A route that wraps the endpoint in DI wiring"""

    def __init__(
        self,
        path: str,
        endpoint: typing.Callable,
        *,
        methods: typing.List[str] = None,
        name: str = None,
        include_in_schema: bool = True
    ) -> None:
        super().__init__(path, wrap_endpoint(endpoint), methods=methods, name=name, include_in_schema=include_in_schema)


class DIMiddleware(BaseHTTPMiddleware):
    """Needed to hold a reference to the container and inject it into each request"""

    def __init__(self, app, *, container: Container) -> None:
        super().__init__(app)
        self.container = container

    async def dispatch(
        self, request: Request, call_next: typing.Callable[[Request], typing.Awaitable[Response]]
    ) -> Response:
        request.state.container = self.container
        return await call_next(request)


# Define our data and routes
@dataclass
class HomeBody:
    param1: str
    param2: int


async def expect_body(body: HomeBody = Body()):
    assert body == HomeBody("abc", 123)
    return Response()


def expect_none(body: HomeBody = Body(None)):
    assert body is None
    return Response()


app = Starlette(
    debug=True,
    routes=[
        DIRoute("/expect-body", expect_body, methods=["POST"]),
        DIRoute("/expect-none", expect_none, methods=["POST"]),
    ],
)

app.add_middleware(DIMiddleware, container=Container())


# Test
from starlette.testclient import TestClient  # noqa

client = TestClient(app)
resp = client.post("/expect-body", json={"param1": "abc", "param2": 123})
assert resp.status_code == 200
try:
    client.post("/expect-body")
except Exception as e:
    assert type(e) is TypeError
resp = client.post("/expect-none")
assert resp.status_code == 200
