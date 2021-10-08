from __future__ import annotations

import contextlib
from typing import Any, Callable

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Route

from di import Container, Dependant, UnwiredDependant


class WiredGetRoute(Route):
    def __init__(
        self,
        path: str,
        endpoint: Callable[..., Any],
        *,
        container: Container,
    ) -> None:

        solved_endpoint = container.solve(Dependant(endpoint))

        async def wrapped_endpoint(request: Request) -> Any:
            return await container.execute_async(
                solved_endpoint, values={Request: request}
            )

        super().__init__(path=path, endpoint=wrapped_endpoint, methods=["GET"])  # type: ignore


class App(Starlette):
    def __init__(self, container: Container | None = None, **kwargs: Any) -> None:
        self.container = container or Container()
        self.container.bind(UnwiredDependant(Request), Request)

        @contextlib.asynccontextmanager
        async def lifespan(app: App):
            async with self.container.enter_global_scope("app"):
                if kwargs.get("lifespan", None) is not None:
                    with kwargs.pop("lifepsan"):
                        yield
                else:
                    yield

        super().__init__(lifespan=lifespan, **kwargs)  # type: ignore

    def get(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def wrappper(func: Callable[..., Any]) -> Callable[..., Any]:
            self.router.routes.append(  # type: ignore
                WiredGetRoute(path=path, endpoint=func, container=self.container)
            )
            return func

        return wrappper
