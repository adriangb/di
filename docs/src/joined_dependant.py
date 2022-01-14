from di import Container, Dependant
from di.dependant import JoinedDependant


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
        a = container.execute_sync(solved)
    assert isinstance(a, A)
    assert B.executed
