import os
from dataclasses import dataclass, field

from di import Container, Dependant, Depends


@dataclass
class Config:
    host: str = field(default_factory=lambda: os.getenv("HOST", "localhost"))


class DBConn:
    def __init__(self, config: Config) -> None:
        self.host = config.host

    async def __call__(self: "DBConn") -> "DBConn":
        print("do database stuff!")
        return self


async def controller(
    conn: DBConn, conn_executed: DBConn = Depends(DBConn.__call__)
) -> None:
    assert conn is conn_executed


async def framework():
    container = Container()
    await container.execute(Dependant(controller))
