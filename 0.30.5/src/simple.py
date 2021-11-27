from dataclasses import dataclass

from di import Container, Dependant


class A:
    ...


class B:
    ...


@dataclass
class C:
    a: A
    b: B


def main():
    container = Container()
    c = container.execute_sync(container.solve(Dependant(C)))
    assert isinstance(c, C)
    assert isinstance(c.a, A)
    assert isinstance(c.b, B)
