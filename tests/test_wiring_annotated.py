import sys
from typing import Optional, Tuple

if sys.version_info < (3, 9):
    from typing_extensions import Annotated
else:
    from typing import Annotated

from di import Container, Dependant, Marker, SyncExecutor
from di.container import bind_by_type


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

    dep = Dependant(f)
    subdeps = dep.get_dependencies()
    assert [d.dependency.call for d in subdeps] == [g, G, g, g]


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
