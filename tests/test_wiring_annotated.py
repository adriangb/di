import sys
from typing import Optional

if sys.version_info < (3, 9):
    from typing_extensions import Annotated
else:
    from typing import Annotated

from di import Container, Dependant, SyncExecutor


def test_wiring_based_from_annotation() -> None:
    def g() -> int:
        return 1

    class G:
        pass

    dep_a = Dependant(g)
    dep_b = "foo bar baz!"
    dep_c = Dependant(g, share=False)
    dep_d = Dependant(g)

    def f(
        a: Annotated[int, dep_a],
        b: Annotated[G, dep_b],
        c: Annotated[int, dep_c],
        d: Annotated[Optional[int], dep_d] = None,
    ) -> None:
        pass

    dep = Dependant(f)
    subdeps = dep.get_dependencies()
    for subdep in subdeps:
        if subdep.parameter:
            subdep.dependency.register_parameter(subdep.parameter)
    assert [d.dependency.call for d in subdeps] == [g, G, g, g]
    assert (subdeps[0].dependency, subdeps[2].dependency, subdeps[3].dependency) == (
        dep_a,
        dep_c,
        dep_d,
    )


def test_autowiring_class_with_default_builtin() -> None:
    class A:
        def __init__(self, value: str = "default") -> None:
            self.value = value

    def func(a: A) -> str:
        return a.value

    dep = Dependant(func)
    container = Container(scopes=(None,))
    solved = container.solve(dep)

    with container.enter_scope(None):
        injected_value = container.execute_sync(solved, SyncExecutor())

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
    container = Container(scopes=(None,))
    solved = container.solve(dep)

    with container.enter_scope(None):
        injected_value = container.execute_sync(solved, SyncExecutor())

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
    container = Container(scopes=(None,))
    container.register_by_type(Dependant(lambda: A("bound")), A)
    solved = container.solve(dep)

    with container.enter_scope(None):
        injected_value = container.execute_sync(solved, SyncExecutor())

    assert injected_value == "bound"
