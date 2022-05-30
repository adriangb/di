import os

from di.container import Container
from di.dependant import Dependant, Marker
from di.executors import AsyncExecutor
from di.typing import Annotated


# Framework code
class Request:
    def __init__(self, domain: str) -> None:
        self.domain = domain


async def web_framework():
    container = Container()
    solved = container.solve(
        Dependant(controller, scope="request"), scopes=["singleton", "request"]
    )
    os.environ["domain"] = "bar.example.com"
    async with container.enter_scope("singleton") as state:
        async with container.enter_scope("request") as state:
            res = await container.execute_async(
                solved,
                values={Request: Request("bar.example.com")},
                executor=AsyncExecutor(),
                state=state,
            )
            assert res == 200
        async with container.enter_scope("request") as state:
            res = await container.execute_async(
                solved,
                values={Request: Request("foo.example.com")},
                executor=AsyncExecutor(),
                state=state,
            )
            assert res == 403


# get_domain_from_env gets the "singleton" scope
def get_domain_from_env() -> str:
    return os.environ["domain"]


# authorize gets the "request" scope
def authorize(
    request: Request,
    domain: Annotated[str, Marker(get_domain_from_env)],
) -> bool:
    return request.domain == domain


async def controller(authorized: Annotated[bool, Marker(authorize)]) -> int:
    if authorized:
        return 200
    return 403
