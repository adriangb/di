import sys
from dataclasses import dataclass

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

from di import AsyncExecutor, Container, Dependant


class DBProtocol(Protocol):
    async def execute(self, sql: str) -> None:
        ...


async def controller(db: DBProtocol) -> None:
    await db.execute("SELECT *")


@dataclass
class DBConfig:
    host: str = "localhost"


class Postgres(DBProtocol):
    def __init__(self, config: DBConfig) -> None:
        self.host = config.host

    async def execute(self, sql: str) -> None:
        print(sql)


async def framework() -> None:
    container = Container(scopes=("request",))
    container.register_by_type(Dependant(Postgres, scope="request"), DBProtocol)
    solved = container.solve(Dependant(controller, scope="request"))
    # this next line would fail without the bind
    async with container.enter_scope("request"):
        await container.execute_async(solved, executor=AsyncExecutor())
    # and we can double check that the bind worked
    # by requesting the instance directly
    async with container.enter_scope("request"):
        db = await container.execute_async(
            container.solve(Dependant(DBProtocol)), executor=AsyncExecutor()
        )
    assert isinstance(db, Postgres)
