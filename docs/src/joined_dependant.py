from di import Container, Dependant, JoinedDependant, SyncExecutor


class A:
    ...


class B:
    executed = False

    def __init__(self) -> None:
        B.executed = True


def main():
    container = Container(scopes=("request",))
    dependant = JoinedDependant(
        Dependant(A, scope="request"),
        siblings=[Dependant(B, scope="request")],
    )
    solved = container.solve(dependant)
    with container.enter_scope("request"):
        a = container.execute_sync(solved, executor=SyncExecutor())
    assert isinstance(a, A)
    assert B.executed
