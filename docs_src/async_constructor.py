from dataclasses import dataclass

from di import AsyncExecutor, Container, Dependant, Marker


class HTTPClient:
    pass


@dataclass
class B:
    msg: str

    @classmethod
    def __di_dependency__(cls) -> Marker:
        # note that client is injected by di!
        async def func(client: HTTPClient) -> B:
            # do an http rquest or something
            return B(msg="👋")

        return Marker(func)


async def main() -> None:
    def endpoint(b: B) -> str:
        return b.msg

    container = Container()
    executor = AsyncExecutor()
    solved = container.solve(Dependant(endpoint))
    async with container.enter_scope(None):
        res = await container.execute_async(solved, executor=executor)
        assert res == "👋"
