from typing import Any, List, Mapping

import pytest

from di.api.dependencies import DependencyParameter
from di.api.providers import DependencyProvider
from di.container import Container, bind_by_type
from di.dependant import Dependant, JoinedDependant, Marker
from di.exceptions import (
    ScopeViolationError,
    SolvingError,
    UnknownScopeError,
    WiringError,
)
from di.executors import SyncExecutor
from di.typing import Annotated


def test_no_annotations_no_default_value_no_marker():
    def badfunc(value):  # type: ignore # for Pylance
        raise AssertionError("This function should never be called")

    def root(v: Annotated[None, Marker(badfunc)]) -> None:  # type: ignore
        raise AssertionError("This function should never be called")

    dep_root = Dependant(root)

    container = Container()

    with pytest.raises(
        WiringError,
        match="You must either provide a dependency marker, a type annotation or a default value",
    ) as exc_info:
        container.solve(dep_root, scopes=[None])
    assert [d.call for d in exc_info.value.path] == [root, badfunc]


def test_default_argument():
    """No type annotations are required if default values are provided"""

    def default_func(value=2) -> int:  # type: ignore # for Pylance
        return value

    container = Container()

    with container.enter_scope(None) as state:
        res = container.execute_sync(
            container.solve(Dependant(default_func), scopes=[None]),
            executor=SyncExecutor(),
            state=state,
        )
    assert res == 2


def test_marker():
    """No type annotations or default value are required if a marker is used"""

    def marker_default_func(value: Annotated[Any, Marker(lambda: 2)]) -> int:
        return value  # type: ignore # for Pylance

    container = Container()

    with container.enter_scope(None) as state:
        res = container.execute_sync(
            container.solve(Dependant(marker_default_func), scopes=[None]),
            executor=SyncExecutor(),
            state=state,
        )
    assert res == 2


def test_dissalow_depending_on_inner_scope():
    """A dependency cannot depend on sub-dependencies that are scoped to a narrower scope"""

    def A() -> None:
        ...

    def B(a: Annotated[None, Marker(A, scope="inner")]):
        ...

    container = Container()

    dep = Dependant(B, scope="outer")

    match = r"scope \(inner\) is narrower than .+'s scope \(outer\)"
    with pytest.raises(ScopeViolationError, match=match):
        container.solve(dep, scopes=["outer", "inner"])


def test_dependency_with_multiple_scopes():
    def A() -> None:
        ...

    def B(
        a1: Annotated[None, Marker(A, scope="app")],
        a2: Annotated[None, Marker(A, scope="request")],
    ) -> None:
        ...

    container = Container()
    with pytest.raises(SolvingError, match="used with multiple scopes"):
        container.solve(Dependant(B, scope="request"), scopes=["app", "request"])


def test_siblings() -> None:
    class DepOne:
        calls: int = 0

        def __call__(self) -> int:
            self.calls += 1
            return 1

    dep1 = DepOne()

    class Sibling:
        called = False

        def __call__(self, one: Annotated[int, Marker(dep1)]) -> None:
            assert one == 1
            self.called = True

    def dep2(one: Annotated[int, Marker(dep1)]) -> int:
        return one + 1

    container = Container()

    siblings = [Sibling(), Sibling()]
    dep = JoinedDependant(Dependant(dep2), siblings=[Dependant(s) for s in siblings])
    solved = container.solve(dep, scopes=[None])
    with container.enter_scope(None) as state:
        container.execute_sync(solved, executor=SyncExecutor(), state=state)
    assert all(s.called for s in siblings)
    assert dep1.calls == 1  # they all use_cached the dependency


def test_non_executable_siblings_is_included_in_dag_but_not_executed() -> None:
    container = Container()

    # sibling should be ignored and excluded from the dag
    main_dep = Dependant(lambda: 1)
    sibling = Dependant[Any](None)
    dep = JoinedDependant(main_dep, siblings=[sibling])
    solved = container.solve(dep, scopes=[None])
    assert [p.dependency for p in solved.dag[dep]] == [sibling]
    assert sibling in solved.dag
    with container.enter_scope(None) as state:
        res = container.execute_sync(solved, executor=SyncExecutor(), state=state)
        assert 1 == res


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

    solved = container.solve(CustomDependant(takes_no_parameters), scopes=[None])

    # should_be_called is called, but it's return value is not passed into
    # takes_no_parameters since the DependencyParameter has parameter=None
    with container.enter_scope(None) as state:
        container.execute_sync(
            solved,
            executor=SyncExecutor(),
            state=state,
        )
    assert calls == 1


class CannotBeWired:
    def __init__(self, arg) -> None:  # type: ignore # for Pylance
        assert arg == 1  # a sentinal value to make sure a bug didn't inject something


def test_no_wire() -> None:
    """Specifying wire=False skips wiring on the dependency itself"""

    container = Container()
    with pytest.raises(WiringError):
        container.solve(Dependant(CannotBeWired), scopes=[None])
    container.solve(Dependant(CannotBeWired, wire=False), scopes=[None])


def test_wiring_from_binds() -> None:
    """Unwirable dependencies will be wired from binds if a bind exists"""

    class CanBeWired(CannotBeWired):
        def __init__(self) -> None:
            super().__init__(1)

    container = Container()
    # container.register_by_type(Dependant(CanBeWired), CannotBeWired)
    with pytest.raises(WiringError):
        container.solve(Dependant(CannotBeWired), scopes=[None])
    container.bind(bind_by_type(Dependant(CanBeWired), CannotBeWired))
    with container.enter_scope(None) as state:
        c = container.execute_sync(
            container.solve(Dependant(CannotBeWired), scopes=[None]),
            executor=SyncExecutor(),
            state=state,
        )
    assert isinstance(c, CanBeWired)


def test_unknown_scope():
    def bad_dep(v: Annotated[int, Marker(lambda: 1, scope="app")]) -> int:
        return v

    container = Container()
    with pytest.raises(UnknownScopeError):
        container.solve(Dependant(bad_dep), scopes=[None])


def test_re_used_dependant() -> None:
    def dep1() -> None:
        ...

    Dep1 = Annotated[None, Marker(dep1)]

    def dep2(one: Dep1) -> None:
        ...

    def dep3(
        one: Dep1,
        two: Annotated[None, Marker(dep2)],
    ) -> None:
        ...

    container = Container()
    container.solve(Dependant(dep3, scope=None), scopes=[None])


def call1():
    ...


def call2(c1: Annotated[None, Marker(call1)]):
    ...


def call3():
    ...


def call4(c2: Annotated[None, Marker(call2)], *, c3: Annotated[None, Marker(call3)]):
    ...


def call5(*, c4: Annotated[None, Marker(call4)]):
    ...


def call6(c4: Annotated[None, Marker(call4)]):
    ...


def call7(c6: Annotated[None, Marker(call6)], c2: Annotated[None, Marker(call2)]):
    ...


@pytest.mark.parametrize(
    "dep,expected",
    [
        (
            call7,
            {
                call1: [],
                call2: [call1],
                call3: [],
                call4: [call2, call3],
                call6: [call4],
                call7: [call6, call2],
            },
        ),
        (
            call6,
            {
                call1: [],
                call2: [call1],
                call3: [],
                call4: [call2, call3],
                call6: [call4],
            },
        ),
        (
            call5,
            {
                call1: [],
                call2: [call1],
                call3: [],
                call4: [call2, call3],
                call5: [call4],
            },
        ),
        (call4, {call1: [], call2: [call1], call3: [], call4: [call2, call3]}),
        (call3, {call3: []}),
        (call2, {call1: [], call2: [call1]}),
        (call1, {call1: []}),
    ],
)
def test_solved_dag(
    dep: DependencyProvider,
    expected: Mapping[DependencyProvider, List[DependencyProvider]],
) -> None:
    container = Container()

    dag = container.solve(Dependant(call=dep), scopes=[None]).dag
    got = {d.call: [s.dependency.call for s in dag[d]] for d in dag}

    assert got == expected
