from dataclasses import dataclass

from di import AsyncExecutor, Container, Dependant, Marker
from di.typing import Annotated


async def get_msg() -> str:
    # make an http request or something
    return "👋"


@dataclass
class B:
    msg: Annotated[str, Marker(get_msg)]


async def main() -> None:
    def endpoint(b: B) -> str:
        return b.msg

    container = Container()
    executor = AsyncExecutor()
    solved = container.solve(Dependant(endpoint))
    async with container.enter_scope(None):
        res = await container.execute_async(solved, executor=executor)
        assert res == "👋"
