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
    def use_value(self, value: int) -> None:
        print(value)


async def controller(request: Request, myobj: MyClass) -> int:
    myobj.use_value(request.value)
    return request.value + 1
