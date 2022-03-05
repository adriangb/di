from dataclasses import dataclass

from di import Container, SyncExecutor
from di.dependant import Dependant, Injectable


def test_injectable_class_scope() -> None:
    @dataclass
    class Bar(Injectable, scope="app"):
        pass

    def func(item: Bar) -> Bar:
        return item

    container = Container()
    dep = Dependant(func, scope="app")
    solved = container.solve(dep, scopes=["app"])

    assert next(iter(solved.dag[dep])).dependency.scope == "app"


def test_injectable_class_call() -> None:
    @dataclass
    class Bar(Injectable, call=lambda: Bar("123")):
        foo: str

    def func(item: Bar) -> Bar:
        return item

    container = Container()
    dep = Dependant(func)
    solved = container.solve(dep, scopes=[None])
    executor = SyncExecutor()
    with container.enter_scope(None) as state:
        item = container.execute_sync(solved, executor, state=state)
        assert item.foo == "123"
