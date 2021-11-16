from di import Container, Dependant


# Framework code
class Request:
    def __init__(self, value: int) -> None:
        self.value = value


async def web_framework():
    container = Container()
    solved = container.solve(Dependant(controller))
    res = await container.execute_async(solved, values={Request: Request(1)})
    assert res == 2


# User code
class MyClass:
    def __init__(self, request: Request) -> None:
        self.value = request.value

    def add(self, value: int) -> int:
        return self.value + value


async def controller(myobj: MyClass) -> int:
    return myobj.add(1)
