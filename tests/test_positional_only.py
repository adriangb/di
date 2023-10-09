from di import Container
from di.dependent import Dependent
from di.executors import SyncExecutor


class Test:
    pass


def test_positional_only_parameters():
    def func(one: Test, /) -> None:
        ...

    container = Container()
    solved = container.solve(Dependent(func), scopes=[None])
    with container.enter_scope(None) as state:
        solved.execute_sync(executor=SyncExecutor(), state=state)
