import pytest

from anydep.container import Container
from anydep.models import Dependant


class Request:
    def __init__(self, value: int = 0) -> None:
        self.value = value


def endpoint(r: Request) -> int:
    return r.value


@pytest.mark.anyio
async def test_bind():
    container = Container()
    async with container.enter_scope("app"):
        r = await container.resolve(endpoint)
        assert r == 0  # just the default value
        async with container.enter_scope("request"):
            request = Request(2)  # build a request
            container.bind(Request, Dependant(lambda: request))  # bind the request
            r = await container.resolve(endpoint)
            assert r == 2  # bound value
        r = await container.resolve(endpoint)
        assert r == 0  # back to the default value
