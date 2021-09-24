import typing

from di.container import Container
from di.models import Dependant
from starlette.requests import Request
from starlette.routing import Route as StarletteRoute


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


class Route(StarletteRoute):
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
        super().__init__(
            path,
            wrap_endpoint(endpoint),
            methods=methods,
            name=name,
            include_in_schema=include_in_schema,
        )
