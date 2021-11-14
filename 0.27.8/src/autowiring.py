import os
from dataclasses import dataclass, field

from di import Container, Dependant


@dataclass
class Config:
    host: str = field(default_factory=lambda: os.getenv("HOST", "localhost"))


class DBConn:
    def __init__(self, config: Config) -> None:
        self.host = config.host


async def controller(conn: DBConn) -> None:
    assert isinstance(conn, DBConn)


async def framework():
    container = Container()
    await container.execute_async(container.solve(Dependant(controller)))
