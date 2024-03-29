from typing import Optional, Tuple

from di import Container, bind_by_type
from di.dependent import Dependent, Marker
from di.executors import SyncExecutor
from di.typing import Annotated


def test_wiring_based_from_annotation() -> None:
    def g() -> int:
        return 1

    class G:
        pass

    dep_a = Marker(g)
    dep_b = "foo bar baz!"
    dep_c = Marker(g, use_cache=False)
    dep_d = Marker(g)

    def f(
        a: Annotated[int, dep_a],
        b: Annotated[G, dep_b],
        c: Annotated[int, dep_c],
        d: Annotated[Optional[int], dep_d] = None,
    ) -> None:
        pass

    dep = Dependent(f)
    subdeps = dep.get_dependencies()
    assert [d.dependency.call for d in subdeps] == [g, G, g, g]


def test_autowiring_class_with_default_builtin() -> None:
    class A:
        def __init__(self, value1: str = "default", value2: int = 1) -> None:
            self.value1 = value1
            self.value2 = value2

    def func(a: A) -> Tuple[str, int]:
        return (a.value1, a.value2)

    dep = Dependent(func)
    container = Container()
    solved = container.solve(dep, scopes=[None])

    with container.enter_scope(None) as state:
        injected_values = solved.execute_sync(SyncExecutor(), state=state)

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

    dep = Dependent(func)
    container = Container()
    solved = container.solve(dep, scopes=[None])

    with container.enter_scope(None) as state:
        injected_value = solved.execute_sync(SyncExecutor(), state=state)

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

    dep = Dependent(func)
    container = Container()
    container.bind(bind_by_type(Dependent(lambda: A("bound")), A))
    solved = container.solve(dep, scopes=[None])

    with container.enter_scope(None) as state:
        injected_value = solved.execute_sync(SyncExecutor(), state=state)

    assert injected_value == "bound"
