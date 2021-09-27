from di import Container, Dependant, Depends


class Request:
    ...


class DBConnection:
    def __init__(self, request: Request) -> None:
        ...


def controller(conn: DBConnection = Depends(scope="app")) -> None:
    ...


async def framework() -> None:
    container = Container()
    async with container.enter_global_scope("app"):
        async with container.enter_local_scope("request"):
            request = Request()
            with container.bind(Dependant(lambda: request, scope="request"), Request):
                await container.execute(Dependant(controller))
