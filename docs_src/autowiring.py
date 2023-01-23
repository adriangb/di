from dataclasses import dataclass

from di import Container
from di.dependent import Dependent
from di.executors import AsyncExecutor


@dataclass
class Config:
    host: str = "localhost"


class DBConn:
    def __init__(self, config: Config) -> None:
        self.host = config.host


async def endpoint(conn: DBConn) -> None:
    assert isinstance(conn, DBConn)


async def framework():
    container = Container()
    solved = container.solve(Dependent(endpoint, scope="request"), scopes=["request"])
    async with container.enter_scope("request") as state:
        await solved.execute_async(executor=AsyncExecutor(), state=state)
