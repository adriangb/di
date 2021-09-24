import typing

from di.container import Container
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class DIMiddleware(BaseHTTPMiddleware):
    """Needed to hold a reference to the container and inject it into each request"""

    def __init__(self, app, *, container: Container) -> None:
        super().__init__(app)
        self.container = container

    async def dispatch(
        self,
        request: Request,
        call_next: typing.Callable[[Request], typing.Awaitable[Response]],
    ) -> Response:
        request.state.container = self.container  # type: ignore
        return await call_next(request)
