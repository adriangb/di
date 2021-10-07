from typing import Generator

from di import Container, Dependant


def test_default_scope() -> None:
    def dep() -> Generator[int, None, None]:
        yield 1

    container = Container(default_scope=1234)

    res = container.execute_sync(container.solve(Dependant(dep, scope=1234)))
    assert res == 1
