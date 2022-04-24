from typing import Tuple

from di.container import Container, bind_by_type
from di.dependant import Dependant
from di.executors import SyncExecutor


def test_autowiring_class_with_default_builtin() -> None:
    class A:
        def __init__(self, value1: str = "default", value2: int = 1) -> None:
            self.value1 = value1
            self.value2 = value2

    def func(a: A) -> Tuple[str, int]:
        return (a.value1, a.value2)

    dep = Dependant(func)
    container = Container()
    solved = container.solve(dep, scopes=[None])

    with container.enter_scope(None) as state:
        injected_values = container.execute_sync(solved, SyncExecutor(), state=state)

    assert injected_values == ("default", 1)


def test_autowiring_class_with_default_class() -> None:
    class A:
        def __init__(self, value: str) -> None:
            self.value = value

    class B:
        def __init__(self, a: A = A("default")) -> None:
            self.a = a

    def func(b: B) -> str:
        return b.a.value

    dep = Dependant(func)
    container = Container()
    solved = container.solve(dep, scopes=[None])

    with container.enter_scope(None) as state:
        injected_value = container.execute_sync(solved, SyncExecutor(), state=state)

    assert injected_value == "default"


def test_autowiring_class_with_default_class_from_bind() -> None:
    class A:
        def __init__(self, value: str) -> None:
            self.value = value

    class B:
        def __init__(self, a: A = A("default")) -> None:
            self.a = a

    def func(b: B) -> str:
        return b.a.value

    dep = Dependant(func)
    container = Container()
    container.bind(bind_by_type(Dependant(lambda: A("bound")), A))
    solved = container.solve(dep, scopes=[None])

    with container.enter_scope(None) as state:
        injected_value = container.execute_sync(solved, SyncExecutor(), state=state)

    assert injected_value == "bound"
