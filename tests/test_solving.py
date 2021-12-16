import sys
from typing import Any, Callable, List, Mapping

from di.dependant import JoinedDependant

if sys.version_info < (3, 8):
    from typing_extensions import Literal
else:
    from typing import Literal

import pytest

from di import Container, Dependant, Depends
from di.api.dependencies import DependantBase, DependencyParameter
from di.api.providers import DependencyProvider
from di.exceptions import ScopeViolationError, SolvingError, WiringError


def test_no_annotations_no_default_value_no_marker():
    def badfunc(value):
        raise AssertionError("This function should never be called")

    container = Container()

    with pytest.raises(
        WiringError,
        match="You must either provide a dependency marker, a type annotation or a default value",
    ):
        container.execute_sync(container.solve(Dependant(badfunc)))


def test_default_argument():
    """No type annotations are required if default values are provided"""

    def default_func(value=2) -> int:
        return value

    container = Container()

    res = container.execute_sync(container.solve(Dependant(default_func)))
    assert res == 2


def test_marker():
    """No type annotations or default value are required if a marker is used"""

    def marker_default_func(value=Depends(lambda: 2)) -> int:
        return value

    container = Container()

    res = container.execute_sync(container.solve(Dependant(marker_default_func)))
    assert res == 2


def test_invalid_non_callable_annotation():
    """The type annotation value: int is not a valid identifier since 1 is not a callable"""

    def func(value: 1 = Depends()) -> int:
        return value

    container = Container()

    match = "Annotation for value is not a callable class or function"
    with pytest.raises(WiringError, match=match):
        container.execute_sync(container.solve(Dependant(func)))


def func1(value: Literal[1] = Depends()) -> int:
    return value


def func2(value: int = Depends()) -> int:
    return value


@pytest.mark.parametrize("function, annotation", [(func1, Literal[1]), (func2, int)])
def test_valid_non_callable_annotation(
    function: Callable[[int], int], annotation: type
):
    """No type annotations are required if default values are provided"""

    container = Container()
    container.bind(Dependant(lambda: 1), annotation)
    res = container.execute_sync(container.solve(Dependant(function)))
    assert res == 1


def test_dissalow_depending_on_inner_scope():
    """A dependency cannot depend on sub-dependencies that are scoped to a narrower scope"""

    def A() -> None:
        ...

    def B(a: None = Depends(A, scope="inner")):
        ...

    container = Container()
    with container.enter_scope("outer"):
        with container.enter_scope("inner"):
            match = r"scope \(inner\) is narrower than .+'s scope \(outer\)"
            with pytest.raises(ScopeViolationError, match=match):
                container.execute_sync(container.solve(Dependant(B, scope="outer")))


def test_dependency_with_multiple_scopes():
    def A() -> None:
        ...

    def B(a: None = Depends(A, scope="app")):
        ...

    def C(a: None = Depends(A, scope="request")):
        ...

    def D(b: None = Depends(B), c: None = Depends(C)):
        ...

    container = Container()
    with container.enter_scope("app"):
        with container.enter_scope("request"):
            match = r"have the same lookup \(__hash__ and __eq__\) but have different scopes"
            with pytest.raises(SolvingError, match=match):
                container.execute_sync(container.solve(Dependant(D)))


def test_siblings() -> None:
    class DepOne:
        calls: int = 0

        def __call__(self) -> int:
            self.calls += 1
            return 1

    dep1 = DepOne()

    class Sibling:
        called = False

        def __call__(self, one: int = Depends(dep1)) -> None:
            assert one == 1
            self.called = True

    def dep2(one: int = Depends(dep1)) -> int:
        return one + 1

    container = Container()

    siblings = [Sibling(), Sibling()]
    dep = JoinedDependant(Dependant(dep2), siblings=[Dependant(s) for s in siblings])
    solved = container.solve(dep)
    container.execute_sync(solved)
    assert all(s.called for s in siblings)
    assert dep1.calls == 1  # they all shared the dependency


def test_non_parameter_dependency():
    """Dependencies can be declared as not call parameters but rather just computationally required"""

    calls: List[bool] = []

    class CustomDependant(Dependant[None]):
        called: bool = False

        def gather_dependencies(
            self, binds: Mapping[DependencyProvider, DependantBase[Any]]
        ) -> List[DependencyParameter]:
            return [
                DependencyParameter(Dependant(call=lambda: calls.append(True)), None)
            ]

    container = Container()

    dep = CustomDependant(lambda: None)
    container.execute_sync(container.solve(dep))
    assert calls == [True]


class CannotBeWired:
    def __init__(self, arg) -> None:
        assert arg == 1  # a sentinal value to make sure a bug didn't inject something


def test_no_autowire() -> None:
    """Specifying autowire=False skips autowiring non explicit sub dependencies"""

    def collect(bad: CannotBeWired) -> None:
        ...

    container = Container()
    with pytest.raises(WiringError):
        container.solve(Dependant(collect))
    container.solve(Dependant(collect, autowire=False))


def test_no_wire() -> None:
    """Specifying wire=False skips wiring on the dependency itself"""

    container = Container()
    with pytest.raises(WiringError):
        container.solve(Dependant(CannotBeWired))
    container.solve(Dependant(CannotBeWired, wire=False))


def test_wiring_from_binds() -> None:
    """Unwirable dependencies will be wired from binds if a bind exists"""

    class CanBeWired(CannotBeWired):
        def __init__(self) -> None:
            super().__init__(1)

    container = Container()
    # container.bind(Dependant(CanBeWired), CannotBeWired)
    with pytest.raises(WiringError):
        container.solve(Dependant(CannotBeWired))
    container.bind(Dependant(CanBeWired), CannotBeWired)  # type: ignore[arg-type]
    c = container.execute_sync(container.solve(Dependant(CannotBeWired)))
    assert isinstance(c, CanBeWired)
