import sys
from dataclasses import dataclass

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

from di.container import Container, bind_by_type
from di.dependent import Dependent
from di.executors import AsyncExecutor


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
    container = Container()
    container.bind(bind_by_type(Dependent(Postgres, scope="request"), DBProtocol))
    solved = container.solve(Dependent(controller, scope="request"), scopes=["request"])
    # this next line would fail without the bind
    async with container.enter_scope("request") as state:
        await container.execute_async(solved, executor=AsyncExecutor(), state=state)
    # and we can double check that the bind worked
    # by requesting the instance directly
    async with container.enter_scope("request") as state:
        db = await container.execute_async(
            container.solve(Dependent(DBProtocol), scopes=["request"]),
            executor=AsyncExecutor(),
            state=state,
        )
    assert isinstance(db, Postgres)
