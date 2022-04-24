import pytest

from di.container import Container, bind_by_type
from di.dependant import Dependant, Marker
from di.executors import SyncExecutor
from di.typing import Annotated


def test_wiring_mismatched_return_value() -> None:
    def f() -> int:
        return 1

    def g(v: Annotated[str, Marker(f)]) -> None:
        pass

    container = Container()
    dep = Dependant(g)

    # exception raised because f() returns an int
    # but g(v) expects a string
    with pytest.raises(Exception):
        container.solve(dep, scopes=[None])


def test_wiring_missing_return_value() -> None:
    def f():
        return 1

    def g(v: Annotated[str, Marker(f)]) -> None:
        pass

    container = Container()
    dep = Dependant(g)

    # no error raised because we don't know the return type
    # of f()
    container.solve(dep, scopes=[None])


def test_wiring_returns_subtype() -> None:
    def f() -> float:
        return 1

    def g(v: Annotated[int, Marker(f)]) -> None:
        pass

    container = Container()
    dep = Dependant(g)

    # no error raised because int is a subtype of float
    container.solve(dep, scopes=[None])


def test_wiring_based_from_annotation() -> None:
    def g() -> int:
        return 1

    class G:
        pass

    dep_a = Marker(g)
    dep_b = "foo bar baz!"
    dep_c = Marker(g, use_cache=False)

    def f(
        a: Annotated[int, dep_a],
        b: Annotated[G, dep_b],
        c: Annotated[int, dep_c],
    ) -> None:
        pass

    dep = Dependant(f)
    subdeps = dep.get_dependencies()
    assert [d.dependency.call for d in subdeps] == [g, G, g]


def test_autowiring_class_with_default_builtin() -> None:
    class A:
        def __init__(self, value: str = "default") -> None:
            self.value = value

    def func(a: A) -> str:
        return a.value

    dep = Dependant(func)
    container = Container()
    solved = container.solve(dep, scopes=[None])

    with container.enter_scope(None) as state:
        injected_value = container.execute_sync(solved, SyncExecutor(), state=state)

    assert injected_value == "default"


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
