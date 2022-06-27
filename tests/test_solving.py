from random import random
from typing import Any, Iterable, List, Mapping

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


RandomInt = Annotated[float, Marker(lambda: random(), use_cache=False)]


def test_re_used_marker() -> None:
    def dep2(num: RandomInt) -> float:
        return num

    def dep3(
        num_2: Annotated[float, Marker(dep2)],
        new_num: RandomInt,
    ) -> None:
        assert num_2 != new_num

    container = Container()
    solved = container.solve(Dependant(dep3, scope=None), scopes=[None])
    with container.enter_scope(None) as state:
        container.execute_sync(solved, SyncExecutor(), state=state)


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


def test_infer_scope_1() -> None:
    # This dep must be inferred into the "app" scope
    # because that's the only scope we enter
    # Otherwise we'd get an error

    def dep() -> Iterable[None]:
        yield None

    container = Container()
    solved = container.solve(Dependant(dep), scopes=["app"])
    with container.enter_scope("app") as state:
        container.execute_sync(solved, SyncExecutor(), state=state)


def test_infer_scope_2() -> None:
    # Since None is a known scope, we don't change it

    def dep() -> Iterable[None]:
        yield None

    container = Container()
    solved = container.solve(Dependant(dep), scopes=[None])
    with container.enter_scope(None) as state:
        container.execute_sync(solved, SyncExecutor(), state=state)


def test_infer_scope_3() -> None:
    def db_connection() -> None:
        ...

    def query_param() -> None:
        ...

    def user_function(
        db: Annotated[None, Marker(db_connection, scope="app")],
        param: Annotated[None, Marker(query_param, scope="request")],
    ) -> None:
        ...

    def endpoint(func: Annotated[None, Marker(user_function)]) -> None:
        ...

    container = Container()
    solved = container.solve(
        Dependant(endpoint, scope="request"), scopes=["app", "request"]
    )
    with container.enter_scope("app") as state:
        with container.enter_scope("request", state=state) as state:
            container.execute_sync(solved, SyncExecutor(), state=state)


def test_infer_scope_4() -> None:
    # This dep must be inferred into the "app" scope
    # because that's the only scope we enter
    # Otherwise we'd get an error

    dep1_values = iter((1, -1))

    def dep1() -> int:
        return next(dep1_values)

    def dep2(v1: Annotated[int, Marker(dep1, scope="connection")]) -> int:
        assert v1 == 1  # cached in the connection scope
        return 2

    dep3_values = iter((3, 4))

    def dep3(v2: Annotated[int, Marker(dep2, scope="request")]) -> int:
        return next(dep3_values)

    # we want to check what scope was inferred for dep3
    # so we'll return it's value and make sure it changes
    def final(v3: Annotated[int, Marker(dep3)]) -> int:
        return v3  # should be 3 and then 4

    container = Container()
    solved = container.solve(Dependant(final), scopes=["connection", "request"])
    with container.enter_scope("connection") as conn_state:
        with container.enter_scope("request", state=conn_state) as req_state:
            res = container.execute_sync(solved, SyncExecutor(), state=req_state)
            assert res == 3
            res = container.execute_sync(solved, SyncExecutor(), state=req_state)
            assert res == 3
        with container.enter_scope("request", state=conn_state) as req_state:
            res = container.execute_sync(solved, SyncExecutor(), state=req_state)
            assert res == 4
            res = container.execute_sync(solved, SyncExecutor(), state=req_state)
            assert res == 4


def test_default_scope() -> None:

    connection_ids = [1, 2]

    def db_connection() -> int:
        return connection_ids.pop(0)

    def user_function(
        db: Annotated[int, Marker(db_connection)],
    ) -> int:
        return db

    def endpoint(val: Annotated[int, Marker(user_function)]) -> int:
        return val

    container = Container()
    solved = container.solve(
        Dependant(endpoint, scope="endpoint"),
        scopes=["app", "connection", "endpoint"],
        default_scope="connection",
    )
    # our goal here is to check that user_function and db_connection
    # both got the "connection" scope because that's what we passed as the default
    executor = SyncExecutor()
    with container.enter_scope("app") as app_state:
        with container.enter_scope("connection", state=app_state) as conn_state:
            with container.enter_scope("endpoint", state=conn_state) as endpoint_state:
                val1 = container.execute_sync(solved, executor, state=endpoint_state)
                val2 = container.execute_sync(solved, executor, state=endpoint_state)
                assert val1 == val2
            val3 = container.execute_sync(solved, executor, state=endpoint_state)
            assert val2 == val3
        with container.enter_scope("connection", state=app_state) as conn_state:
            with container.enter_scope("endpoint", state=conn_state) as endpoint_state:
                val4 = container.execute_sync(solved, executor, state=endpoint_state)
                val5 = container.execute_sync(solved, executor, state=endpoint_state)
                assert val4 == val5
            val6 = container.execute_sync(solved, executor, state=endpoint_state)
            assert val5 == val6

    assert (val1, val4) == (1, 2)
