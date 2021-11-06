from di import Container, Dependant
from di.dependant import JoinedDependant


class A:
    ...


class B:
    executed = False

    def __init__(self) -> None:
        B.executed = True


def main():
    container = Container()
    dependant = JoinedDependant(Dependant(A), siblings=[Dependant(B)])
    solved = container.solve(dependant)
    a = container.execute_sync(solved)
    assert isinstance(a, A)
    assert B.executed
