import typing
from contextlib import asynccontextmanager
from dataclasses import dataclass

from di.container import Container
from di.params import Depends
from pydantic import BaseModel
from starlette.responses import Response
from starlette.testclient import TestClient

from comparisons.asgi.application import App
from comparisons.asgi.body import Body
from comparisons.asgi.headers import Header
from comparisons.asgi.routing import Route


class PydanticNested(BaseModel):
    int_field: int
    str_field_default: str = "test"


class PydanticBody(BaseModel):
    submodel: PydanticNested
    param2: int


@dataclass
class DataclassNested:
    int_field: int
    str_field_default: str = "test"


@dataclass
class DataclassBody:
    submodel: DataclassNested
    param2: int


class DBConnection:
    _state: str = "disconnected"

    @property
    def state(self):
        return self.__class__._state

    @state.setter
    def state(self, v):
        self.__class__._state = v


@asynccontextmanager
async def create_connection() -> typing.AsyncGenerator[DBConnection, None]:
    """something like asyncpg.create_connection"""
    conn = DBConnection()
    conn.state = "connected"
    yield conn
    conn.state = "disconnected"


DBContainerDep: DBConnection = Depends(scope="lifespan")


async def pydantic_endpoint(
    body: PydanticBody = Body(),
    x_my_header: int = Header(),
    conn: DBConnection = DBContainerDep,
):
    assert body == PydanticBody(
        submodel=PydanticNested(int_field=1, str_field_default="test"), param2=1234
    )
    assert x_my_header == 1234
    assert conn.state == "connected"
    return Response()


async def dataclass_endpoint(
    body: DataclassBody = Body(),
    x_my_header: int = Header(),
    conn: DBConnection = DBContainerDep,
):
    assert body == DataclassBody(DataclassNested(1, "test"), 1234)
    assert x_my_header == 1234
    assert conn.state == "connected"
    return Response()


async def lifespan(container: Container):  # request the container to be injected
    # bind in lifespan scope so that di will handle teardown automatically
    async with create_connection() as conn:
        container.bind(DBConnection, lambda: conn)
        yield


app = App(
    routes=[
        Route("/dataclass", dataclass_endpoint, methods=["POST"]),
        Route("/pydantic", pydantic_endpoint, methods=["POST"]),
    ],
    lifespan=lifespan,
)


assert DBConnection._state == "disconnected"
with TestClient(app) as client:
    payload = {"submodel": {"int_field": 1}, "param2": 1234}
    headers = {"X-My-Header": "1234"}

    resp = client.post("/dataclass", json=payload, headers=headers)
    assert resp.status_code == 200
    assert DBConnection._state == "connected"

    resp = client.post("/pydantic", json=payload, headers=headers)
    assert resp.status_code == 200
    assert DBConnection._state == "connected"

    # play around w/ binds, a natural way to override a dependency
    class FakeDBConnection:
        state = "disconnected"

    app.container.bind(
        DBConnection, FakeDBConnection
    )  # maybe want a context manager here?
    try:
        client.post("/pydantic", json=payload, headers=headers)
    except AssertionError:
        pass
    else:
        raise AssertionError

assert DBConnection._state == "disconnected"
