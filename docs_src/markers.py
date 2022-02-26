from dataclasses import dataclass

from di import Container, Dependant, Marker, SyncExecutor
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
    container = Container(scopes=["request"])
    solved = container.solve(Dependant(endpoint, scope="request"))
    with container.enter_scope("request"):
        container.execute_sync(solved, executor=SyncExecutor())
