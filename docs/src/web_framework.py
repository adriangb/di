from di.container import Container
from di.dependency import Dependant


class Request:
    def __init__(self, value: int) -> None:
        self.value = value


async def controller(request: Request) -> int:
    return request.value + 1


async def web_framework():
    container = Container()
    async with container.enter_local_scope("request"):
        request = Request(1)
        request_provider = Dependant(lambda: request, scope="request")
        container.bind(request_provider, Request, scope="request")
        res = await container.execute(Dependant(controller))
        assert res == 2
