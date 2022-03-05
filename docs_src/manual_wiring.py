import os
import sys
from dataclasses import dataclass, field

if sys.version_info < (3, 9):
    from typing_extensions import Annotated
else:
    from typing import Annotated

from di import AsyncExecutor, Container, Dependant, Marker


class AbstractDBConn:
    def execute(self, query: str) -> str:
        ...


@dataclass
class Config:
    host: str = field(default_factory=lambda: os.getenv("HOST", "localhost"))


class ConcreteDBConn:
    def __init__(self, config: Config) -> None:
        self.config = config

    def execute(self, query: str) -> str:
        return f"executed {query}"


def get_user(db: AbstractDBConn) -> str:
    # this is a nonsensical query for demonstration purposes
    # you'd normally want to get the id from the request
    # and returna User object or something like that
    return db.execute("SELECT name from Users LIMIT 1")


async def controller(
    # markers can be added via Annotated
    user1: Annotated[str, Marker(get_user, scope="request")],
    # or as the default value, in which case types can be checked by MyPy/Pylance
    user2: Annotated[str, Marker(get_user, scope="request")],
) -> None:
    assert user1 == user2 == "executed SELECT name from Users LIMIT 1"


async def framework():
    container = Container()
    # note that di will also autowire the bind, in this case to inject Config
    container.bind_by_type(Dependant(ConcreteDBConn, scope="request"), AbstractDBConn)
    solved = container.solve(Dependant(controller, scope="request"), scopes=["request"])
    async with container.enter_scope("request") as state:
        await container.execute_async(solved, executor=AsyncExecutor(), state=state)
