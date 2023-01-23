from dataclasses import dataclass

from di import Container
from di.dependent import Dependent, Marker
from di.executors import SyncExecutor
from di.typing import Annotated


@dataclass
class Config:
    host: str = "localhost"


class DBConn:
    def __init__(self, host: str) -> None:
        self.host = host


def inject_db(config: Config) -> DBConn:
    return DBConn(host=config.host)


def endpoint(conn: Annotated[DBConn, Marker(inject_db, scope="request")]) -> None:
    assert isinstance(conn, DBConn)


def framework():
    container = Container()
    solved = container.solve(Dependent(endpoint, scope="request"), scopes=["request"])
    with container.enter_scope("request") as state:
        solved.execute_sync(executor=SyncExecutor(), state=state)
