from dataclasses import dataclass

from di import AsyncExecutor, Container, Dependant


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
    solved = container.solve(Dependant(endpoint, scope="request"), scopes=["request"])
    async with container.enter_scope("request") as state:
        await container.execute_async(solved, executor=AsyncExecutor(), state=state)
