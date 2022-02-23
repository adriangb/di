from dataclasses import dataclass

from di import Container, SyncExecutor
from di.dependant import Dependant, InjectableClass


def test_injectable_class() -> None:
    class Foo:
        pass

    @dataclass
    class Bar(InjectableClass, scope="app"):
        foo: Foo

    def func(item: Bar) -> Bar:
        return item

    container = Container(scopes=("app", "request"))
    dep = Dependant(func, scope="app")
    solved = container.solve(dep)
    executor = SyncExecutor()
    with container.enter_scope("app"):
        item1 = container.execute_sync(solved, executor)
        item2 = container.execute_sync(solved, executor)
        assert item1 is item2
