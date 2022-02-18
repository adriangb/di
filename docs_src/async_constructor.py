from dataclasses import dataclass

from di import AsyncExecutor, Container, Dependant


@dataclass
class A:
    greeting = "👋"


@dataclass
class B:
    msg: str

    @classmethod
    async def __call__(cls, a: A) -> "B":
        return B(msg=f"{a.greeting} {cls.__name__}")


async def main() -> None:
    def endpoint(b: B) -> str:
        return b.msg

    container = Container()
    executor = AsyncExecutor()
    solved = container.solve(Dependant(endpoint))
    async with container.enter_scope(None):
        res = await container.execute_async(solved, executor=executor)
        assert res == "👋 B"
