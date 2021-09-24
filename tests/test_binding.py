from typing import Tuple

import anyio
import pytest

from di.container import Container
from di.dependency import Dependant
from di.params import Depends


class Request:
    def __init__(self, value: int = 0) -> None:
        self.value = value


def endpoint(r: Request) -> int:
    return r.value


@pytest.mark.anyio
async def test_bind():
    container = Container()
    async with container.enter_global_scope("app"):
        r = await container.execute(Dependant(endpoint))
        assert r == 0  # just the default value
        async with container.enter_local_scope("request"):
            request = Request(2)  # build a request
            container.bind(
                lambda: request, Request, scope="request"
            )  # bind the request
            r = await container.execute(Dependant(endpoint))
            assert r == 2  # bound value
        r = await container.execute(Dependant(endpoint))
        assert r == 0  # back to the default value


def inject1():
    return -1


def inject2():
    return -2


def inject3():
    return -2


async def endpoint2(
    v1: int = Depends(inject1), v2: int = Depends(inject2), v3: int = Depends(inject3)
) -> Tuple[int, int, int]:
    return v1, v2, v3


async def run_endpoint2(expected: Tuple[int, int, int], container: Container):
    async with container.enter_local_scope("request"):
        container.bind(lambda: expected[2], inject3, scope="request")
        got = await container.execute(Dependant(endpoint2))
    assert expected == got, (expected, got)


@pytest.mark.anyio
async def test_concurrent_binds():
    container = Container()
    async with container.enter_local_scope("app-local"):
        container.bind(lambda: -10, inject1, scope="app-local")
        async with container.enter_global_scope("app-global"):
            container.bind(lambda: -20, inject2, scope="app-global")
            async with anyio.create_task_group() as tg:
                for i in range(10):
                    tg.start_soon(run_endpoint2, (-10, -20, i), container)  # type: ignore
