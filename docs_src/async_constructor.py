import inspect
from dataclasses import dataclass

from di import Container
from di.dependent import Dependent
from di.executors import AsyncExecutor


class HTTPClient:
    pass


@dataclass
class B:
    msg: str

    @classmethod
    def __di_dependency__(cls, param: inspect.Parameter) -> "Dependent[B]":
        # note that client is injected by di!
        async def func(client: HTTPClient) -> B:
            # do an http request or something
            return B(msg=f"👋 from {param.name}")

        return Dependent(func)


async def main() -> None:
    def endpoint(b: B) -> str:
        return b.msg

    container = Container()
    executor = AsyncExecutor()
    solved = container.solve(Dependent(endpoint), scopes=(None,))
    async with container.enter_scope(None) as state:
        res = await solved.execute_async(executor=executor, state=state)
        assert res == "👋 from b"
