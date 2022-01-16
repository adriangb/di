from di import Container, Dependant, SyncExecutor
from di.typing import Annotated


class Request:
    ...


class DBConnection:
    def __init__(self, request: Request) -> None:
        ...


def controller(conn: Annotated[DBConnection, Dependant(scope="app")]) -> None:
    ...


def framework() -> None:
    container = Container(scopes=("app", "request"))
    with container.enter_scope("app"):
        with container.enter_scope("request"):
            request = Request()
            with container.bind(Dependant(lambda: request, scope="request"), Request):
                container.execute_sync(
                    container.solve(Dependant(controller)), executor=SyncExecutor()
                )
