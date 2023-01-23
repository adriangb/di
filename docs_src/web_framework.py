from typing import Any, Callable

from di import Container
from di.dependent import Dependent
from di.executors import SyncExecutor


# Framework code
class Request:
    def __init__(self, value: int) -> None:
        self.value = value


class App:
    def __init__(self, controller: Callable[..., Any]) -> None:
        self.container = Container()
        self.solved = self.container.solve(
            Dependent(controller, scope="request"),
            scopes=["request"],
        )
        self.executor = SyncExecutor()

    def run(self, request: Request) -> int:
        with self.container.enter_scope("request") as state:
            return self.solved.execute_sync(
                values={Request: request},
                executor=self.executor,
                state=state,
            )


# User code
class MyClass:
    def __init__(self, request: Request) -> None:
        self.value = request.value

    def add(self, value: int) -> int:
        return self.value + value


def controller(myobj: MyClass) -> int:
    return myobj.add(1)


def main() -> None:
    app = App(controller)
    resp = app.run(Request(1))
    assert resp == 2
    resp = app.run(Request(2))
    assert resp == 3


if __name__ == "__main__":
    main()
