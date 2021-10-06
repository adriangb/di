from contextvars import ContextVar
from typing import List, TypeVar

import anyio

from di import Container, Dependant
from di.types.solved import SolvedDependency

T = TypeVar("T")


class Request:
    ...


class RequestLog(List[Request]):
    ...


request_ctx: ContextVar[Request] = ContextVar("request_ctx")


def get_request() -> Request:
    return request_ctx.get()


async def execute_request(
    request: Request, container: Container, solved: SolvedDependency[T]
) -> T:
    async with container.enter_local_scope("request"):
        token = request_ctx.set(request)
        try:
            return await container.execute_async(solved)
        finally:
            request_ctx.reset(token)


async def framework() -> None:
    container = Container()
    request_log = RequestLog()
    container.bind(Dependant(lambda: request_log, scope="app"), RequestLog)
    container.bind(Dependant(get_request, scope="request"), Request)
    solved = container.solve(Dependant(controller, scope="request"))
    async with container.enter_global_scope("app"):
        # simulate concurrent requests
        n_requests = 25
        async with anyio.create_task_group() as tg:
            for _ in range(n_requests):
                tg.start_soon(execute_request, Request(), container, solved)  # type: ignore

    # make sure we processed n_requests distinct requests
    assert len(request_log) == len(set(request_log)) == n_requests


async def controller(request: Request, request_log: RequestLog) -> None:
    """This is the only piece of user code"""
    request_log.append(request)
