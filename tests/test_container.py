from typing import Generator

from di import Container, Dependant


def test_default_scope() -> None:
    def dep() -> Generator[int, None, None]:
        yield 1

    container = Container(default_scope=1234)

    res = container.execute_sync(container.solve(Dependant(dep, scope=1234)))
    assert res == 1


def test_scopes_property() -> None:
    container = Container()
    assert container.scopes == []
    with container.enter_global_scope("test"):
        assert container.scopes == ["test"]
        with container.enter_local_scope("another"):
            assert container.scopes == ["test", "another"]


def test_binds_property():
    container = Container()
    assert container.binds == {}

    def func() -> None:
        ...

    dep = Dependant(lambda: None)
    container.bind(dep, func)
    assert container.binds == {func: dep}
