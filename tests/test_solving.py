from typing import Any, List

import pytest

from di import Container, Dependant, SyncExecutor
from di.api.dependencies import DependencyParameter
from di.dependant import JoinedDependant
from di.exceptions import ScopeViolationError, UnknownScopeError, WiringError
from di.typing import Annotated


def test_no_annotations_no_default_value_no_marker():
    def badfunc(value):  # type: ignore # for Pylance
        raise AssertionError("This function should never be called")

    container = Container()

    with pytest.raises(
        WiringError,
        match="You must either provide a dependency marker, a type annotation or a default value",
    ):
        with container.enter_scope(None):
            container.execute_sync(container.solve(Dependant(badfunc)), executor=SyncExecutor())  # type: ignore # for Pylance


def test_default_argument():
    """No type annotations are required if default values are provided"""

    def default_func(value=2) -> int:  # type: ignore # for Pylance
        return value  # type: ignore # for Pylance

    container = Container()

    with container.enter_scope(None):
        res = container.execute_sync(container.solve(Dependant(default_func)), executor=SyncExecutor())  # type: ignore # for Pylance
    assert res == 2


def test_marker():
    """No type annotations or default value are required if a marker is used"""

    def marker_default_func(value: Annotated[Any, Dependant(lambda: 2)]) -> int:  # type: ignore # for Pylance
        return value  # type: ignore # for Pylance

    container = Container()

    with container.enter_scope(None):
        res = container.execute_sync(container.solve(Dependant(marker_default_func)), executor=SyncExecutor())  # type: ignore # for Pylance
    assert res == 2


def test_dissalow_depending_on_inner_scope():
    """A dependency cannot depend on sub-dependencies that are scoped to a narrower scope"""

    def A() -> None:
        ...

    def B(a: Annotated[None, Dependant(A, scope="inner")]):
        ...

    container = Container(scopes=("outer", "inner"))
    with container.enter_scope("outer"):
        with container.enter_scope("inner"):
            match = r"scope \(inner\) is narrower than .+'s scope \(outer\)"
            with pytest.raises(ScopeViolationError, match=match):
                container.solve(Dependant(B, scope="outer"))


def test_dependency_with_multiple_scopes():
    def A() -> None:
        ...

    def B(
        a1: Annotated[None, Dependant(A, scope="app")],
        a2: Annotated[None, Dependant(A, scope="request")],
    ) -> None:
        ...

    container = Container(scopes=("app", "request"))
    with pytest.raises(ScopeViolationError, match="used with multiple scopes"):
        container.solve(Dependant(B, scope="request"))


def test_siblings() -> None:
    class DepOne:
        calls: int = 0

        def __call__(self) -> int:
            self.calls += 1
            return 1

    dep1 = DepOne()

    class Sibling:
        called = False

        def __call__(self, one: Annotated[int, Dependant(dep1)]) -> None:
            assert one == 1
            self.called = True

    def dep2(one: Annotated[int, Dependant(dep1)]) -> int:
        return one + 1

    container = Container()

    siblings = [Sibling(), Sibling()]
    dep = JoinedDependant(Dependant(dep2), siblings=[Dependant(s) for s in siblings])
    solved = container.solve(dep)
    with container.enter_scope(None):
        container.execute_sync(solved, executor=SyncExecutor())
    assert all(s.called for s in siblings)
    assert dep1.calls == 1  # they all use_cached the dependency


def test_non_parameter_dependency():
    """Dependencies can be declared as not call parameters but rather just computationally required"""

    calls: int = 0

    def should_be_called() -> None:
        nonlocal calls
        calls += 1

    class CustomDependant(Dependant[None]):
        called: bool = False

        def get_dependencies(self) -> List[DependencyParameter]:
            return [
                DependencyParameter(
                    dependency=Dependant(should_be_called), parameter=None
                )
            ]

    container = Container()

    def takes_no_parameters() -> None:
        pass

    # should_be_called is called, but it's return value is not passed into
    # takes_no_parameters since the DependencyParameter has parameter=None
    with container.enter_scope(None):
        container.execute_sync(
            container.solve(CustomDependant(takes_no_parameters)),
            executor=SyncExecutor(),
        )
    assert calls == 1


class CannotBeWired:
    def __init__(self, arg) -> None:  # type: ignore # for Pylance
        assert arg == 1  # a sentinal value to make sure a bug didn't inject something


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
    # container.register_by_type(Dependant(CanBeWired), CannotBeWired)
    with pytest.raises(WiringError):
        container.solve(Dependant(CannotBeWired))
    container.register_by_type(Dependant(CanBeWired), CannotBeWired)
    with container.enter_scope(None):
        c = container.execute_sync(
            container.solve(Dependant(CannotBeWired)), executor=SyncExecutor()
        )
    assert isinstance(c, CanBeWired)


def test_unknown_scope():
    def bad_dep(v: Annotated[int, Dependant(lambda: 1, scope="app")]) -> int:
        return v

    container = Container()
    with pytest.raises(UnknownScopeError):
        container.solve(Dependant(bad_dep))
