import os
from typing import Any, Sequence

from di import Container
from di.api.dependencies import DependentBase
from di.api.scopes import Scope
from di.dependent import Dependent, Marker
from di.executors import AsyncExecutor
from di.typing import Annotated


# Framework code
class Request:
    def __init__(self, domain: str) -> None:
        self.domain = domain


async def web_framework() -> None:
    container = Container()
    container.bind(
        lambda param, dependent: Dependent(Request, scope="request", wire=False)
        if dependent.call is Request
        else None
    )

    def scope_resolver(
        dep: DependentBase[Any],
        subdep_scopes: Sequence[Scope],
        scopes: Sequence[Scope],
    ) -> Scope:
        if dep.scope is None:
            return "request"
        return dep.scope

    solved = container.solve(
        Dependent(controller, scope="request"),
        scopes=["singleton", "request"],
        scope_resolver=scope_resolver,
    )
    async with container.enter_scope("singleton") as singleton_state:
        os.environ["domain"] = "bar.example.com"
        async with container.enter_scope(
            "request", state=singleton_state
        ) as request_state:
            status = await solved.execute_async(
                values={Request: Request("bar.example.com")},
                executor=AsyncExecutor(),
                state=request_state,
            )
            assert status == 200, status
        os.environ["domain"] = "foo.example.com"
        async with container.enter_scope(
            "request", state=singleton_state
        ) as request_state:
            status = await solved.execute_async(
                values={Request: Request("foo.example.com")},
                executor=AsyncExecutor(),
                state=request_state,
            )
            assert status == 200, status


# get_domain_from_env gets the "request" scope
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
