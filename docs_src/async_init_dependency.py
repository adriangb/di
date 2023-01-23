from dataclasses import dataclass

from di import Container
from di.dependent import Dependent, Marker
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
    solved = container.solve(Dependent(endpoint), scopes=(None,))
    async with container.enter_scope(None) as state:
        res = await solved.execute_async(executor=executor, state=state)
        assert res == "👋"
