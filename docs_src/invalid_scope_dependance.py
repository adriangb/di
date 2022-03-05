from di import Container, Dependant, Marker, SyncExecutor
from di.typing import Annotated


class Request:
    ...


class DBConnection:
    def __init__(self, request: Request) -> None:
        ...


def controller(conn: Annotated[DBConnection, Marker(scope="app")]) -> None:
    ...


def framework() -> None:
    container = Container()
    with container.bind_by_type(Dependant(lambda: request, scope="request"), Request):
        solved = container.solve(Dependant(controller), scopes=["app", "request"])
    with container.enter_scope("app") as app_state:
        with container.enter_scope("request", state=app_state) as request_state:
            request = Request()
            with container.bind_by_type(
                Dependant(lambda: request, scope="request"), Request
            ):
                container.execute_sync(
                    solved, executor=SyncExecutor(), state=request_state
                )
