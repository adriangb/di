import typing

from di.container import Container
from di.models import Dependant
from starlette.applications import Starlette
from starlette.middleware import Middleware

from comparisons.asgi.middleware import DIMiddleware


async def _placeholder(app: "App"):
    yield


class App(Starlette):
    container: Container

    def __init__(self, container: typing.Optional[Container] = None, **kwargs) -> None:
        middleware = kwargs.pop("middleware", None) or []
        self.container = container or Container()
        middleware.insert(0, Middleware(DIMiddleware, container=self.container))
        user_lifespan = kwargs.pop("lifespan", None) or _placeholder

        async def lifespan(app: "App") -> typing.AsyncGenerator[None, None]:
            async with self.container.enter_global_scope("lifespan"):
                self.container.bind(App, lambda: self)
                self.container.bind(Container, lambda: self.container)
                await self.container.execute(Dependant(user_lifespan))  # type: ignore
                yield None

        super().__init__(**kwargs, middleware=middleware, lifespan=lifespan)
