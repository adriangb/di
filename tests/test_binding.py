import anyio
import pytest

from anydep.container import Container
from anydep.params import Depends


class Request:
    def __init__(self, value: int = 0) -> None:
        self.value = value


def endpoint(r: Request) -> int:
    return r.value


@pytest.mark.anyio
async def test_bind():
    container = Container()
    async with container.enter_global_scope("app"):
        r = await container.execute(container.get_dependant(endpoint))
        assert r == 0  # just the default value
        async with container.enter_local_scope("request"):
            request = Request(2)  # build a request
            container.bind(Request, lambda: request)  # bind the request
            r = await container.execute(container.get_dependant(endpoint))
            assert r == 2  # bound value
        r = await container.execute(container.get_dependant(endpoint))
        assert r == 0  # back to the default value


def inject():
    return -1


async def endpoint2(injected: int = Depends(inject)) -> int:
    return injected


async def run_endpoint2(expected: int, container: Container):
    async with container.enter_local_scope("request"):
        container.bind(inject, lambda: expected)
        got = await container.execute(container.get_dependant(endpoint2))
    assert expected == got


@pytest.mark.anyio
async def test_concurrent_binds():
    container = Container()
    async with anyio.create_task_group() as tg:
        for i in range(50):
            tg.start_soon(run_endpoint2, i, container)
