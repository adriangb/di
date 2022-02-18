from dataclasses import dataclass

from di import AsyncExecutor, Container, Dependant
from di.typing import Annotated


@dataclass
class A:
    greeting = "👋"


async def get_greeting(a: A) -> str:
    return a.greeting


@dataclass
class B:
    msg: Annotated[str, Dependant(get_greeting)]


async def main() -> None:
    def endpoint(b: B) -> str:
        return b.msg

    container = Container()
    executor = AsyncExecutor()
    solved = container.solve(Dependant(endpoint))
    async with container.enter_scope(None):
        res = await container.execute_async(solved, executor=executor)
        assert res == "👋"
