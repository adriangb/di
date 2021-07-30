import pytest

from anydep.container import Container


class Request:
    def __init__(self, value: int = 0) -> None:
        self.value = value


def endpoint(r: Request) -> int:
    return r.value


@pytest.mark.anyio
async def test_bind():
    container = Container()
    async with container.enter_scope("app"):
        r = await container.execute(container.get_dependant(endpoint))
        assert r == 0  # just the default value
        async with container.enter_scope("request"):
            request = Request(2)  # build a request
            container.bind(Request, lambda: request)  # bind the request
            r = await container.execute(container.get_dependant(endpoint))
            assert r == 2  # bound value
        r = await container.execute(container.get_dependant(endpoint))
        assert r == 0  # back to the default value
