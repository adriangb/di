from dataclasses import dataclass

from di import Container, SyncExecutor
from di.dependant import Dependant, Injectable


def test_injectable_class_scope() -> None:
    @dataclass
    class Bar(Injectable, scope="app"):
        pass

    def func(item: Bar) -> Bar:
        return item

    container = Container(scopes=("app",))
    dep = Dependant(func, scope="app")
    solved = container.solve(dep)
    executor = SyncExecutor()

    with container.enter_scope("app"):
        item1 = container.execute_sync(solved, executor)
        item2 = container.execute_sync(solved, executor)
        assert item1 is item2

    with container.enter_scope("app"):
        item3 = container.execute_sync(solved, executor)
        assert item3 is not item2


def test_injectable_class_call() -> None:
    @dataclass
    class Bar(Injectable, call=lambda: Bar("123")):
        foo: str

    def func(item: Bar) -> Bar:
        return item

    container = Container(scopes=(None,))
    dep = Dependant(func)
    solved = container.solve(dep)
    executor = SyncExecutor()
    with container.enter_scope(None):
        item = container.execute_sync(solved, executor)
        assert item.foo == "123"
