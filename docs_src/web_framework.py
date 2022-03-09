from di.container import Container
from di.dependant import Dependant
from di.executors import AsyncExecutor


# Framework code
class Request:
    def __init__(self, value: int) -> None:
        self.value = value


async def web_framework():
    container = Container()
    solved = container.solve(Dependant(controller, scope="request"), scopes=["request"])
    async with container.enter_scope("request") as state:
        res = await container.execute_async(
            solved, values={Request: Request(1)}, executor=AsyncExecutor(), state=state
        )
    assert res == 2


# User code
class MyClass:
    def __init__(self, request: Request) -> None:
        self.value = request.value

    def add(self, value: int) -> int:
        return self.value + value


async def controller(myobj: MyClass) -> int:
    return myobj.add(1)
