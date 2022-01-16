from dataclasses import dataclass

from di import Container, Dependant, SyncExecutor


class A:
    ...


class B:
    ...


@dataclass
class C:
    a: A
    b: B


def main():
    container = Container(scopes=["request"])
    solved = container.solve(Dependant(C, scope="request"))
    with container.enter_scope("request"):
        c = container.execute_sync(solved, executor=SyncExecutor())
    assert isinstance(c, C)
    assert isinstance(c.a, A)
    assert isinstance(c.b, B)
