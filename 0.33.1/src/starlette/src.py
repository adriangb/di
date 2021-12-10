from __future__ import annotations

import contextlib
from typing import Any, Callable

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Route

from di import Dependant
from di.api.container import ContainerProtocol
from di.container import BaseContainer


class WiredGetRoute(Route):
    def __init__(
        self,
        path: str,
        endpoint: Callable[..., Any],
        *,
        container: ContainerProtocol,
    ) -> None:

        solved_endpoint = container.solve(Dependant(endpoint))

        async def wrapped_endpoint(request: Request) -> Any:
            app_container: ContainerProtocol = request.app.container
            async with app_container.enter_scope("request") as request_container:
                return await request_container.execute_async(
                    solved_endpoint,
                    values={Request: request},
                )

        super().__init__(path=path, endpoint=wrapped_endpoint, methods=["GET"])  # type: ignore


class App(Starlette):
    def __init__(self) -> None:
        self.container = BaseContainer()
        self.container.bind(Dependant(Request, autowire=False), Request)

        @contextlib.asynccontextmanager
        async def lifespan(app: App):
            async with self.container.enter_scope("app") as container:
                self.container = container
                yield

        super().__init__(lifespan=lifespan)

    def get(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def wrappper(func: Callable[..., Any]) -> Callable[..., Any]:
            self.router.routes.append(  # type: ignore
                WiredGetRoute(path=path, endpoint=func, container=self.container)
            )
            return func

        return wrappper
