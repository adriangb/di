from dataclasses import dataclass

from di.container import Container
from di.dependant import Dependant, Marker
from di.executors import AsyncExecutor
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
    solved = container.solve(Dependant(endpoint), scopes=(None,))
    async with container.enter_scope(None) as state:
        res = await container.execute_async(solved, executor=executor, state=state)
        assert res == "👋"
