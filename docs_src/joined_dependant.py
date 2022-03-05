from di import Container, Dependant, JoinedDependant, SyncExecutor


class A:
    ...


class B:
    executed = False

    def __init__(self) -> None:
        B.executed = True


def main():
    container = Container()
    dependant = JoinedDependant(
        Dependant(A, scope="request"),
        siblings=[Dependant(B, scope="request")],
    )
    solved = container.solve(dependant, scopes=["request"])
    with container.enter_scope("request") as state:
        a = container.execute_sync(solved, executor=SyncExecutor(), state=state)
    assert isinstance(a, A)
    assert B.executed
