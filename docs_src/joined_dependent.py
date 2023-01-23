from di import Container
from di.dependent import Dependent, JoinedDependent
from di.executors import SyncExecutor


class A:
    ...


class B:
    executed = False

    def __init__(self) -> None:
        B.executed = True


def main():
    container = Container()
    dependent = JoinedDependent(
        Dependent(A, scope="request"),
        siblings=[Dependent(B, scope="request")],
    )
    solved = container.solve(dependent, scopes=["request"])
    with container.enter_scope("request") as state:
        a = solved.execute_sync(executor=SyncExecutor(), state=state)
    assert isinstance(a, A)
    assert B.executed
