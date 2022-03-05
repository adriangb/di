from dataclasses import dataclass
from typing import Any, Tuple

from di import Container, Dependant, Marker, SyncExecutor
from di.typing import Annotated


def test_test_caching_within_execution_scope_use_cache_true() -> None:
    values = iter(range(2))

    def dep() -> int:
        return next(values)

    container = Container()
    executor = SyncExecutor()
    solved = container.solve(Dependant(dep), scopes=[None])

    with container.enter_scope(None) as state:
        val = container.execute_sync(solved, executor=executor, state=state)
        assert val == 0
        val = container.execute_sync(solved, executor=executor, state=state)
        assert val == 0

    with container.enter_scope(None) as state:
        val = container.execute_sync(solved, executor=executor, state=state)
        assert val == 1
        val = container.execute_sync(solved, executor=executor, state=state)
        assert val == 1


def test_test_caching_within_execution_scope_use_cache_false() -> None:
    values = iter(range(4))

    def dep() -> int:
        return next(values)

    container = Container()
    executor = SyncExecutor()
    solved = container.solve(Dependant(dep, use_cache=False), scopes=[None])

    with container.enter_scope(None) as state:
        val = container.execute_sync(solved, executor=executor, state=state)
        assert val == 0
        val = container.execute_sync(solved, executor=executor, state=state)
        assert val == 1

    with container.enter_scope(None) as state:
        val = container.execute_sync(solved, executor=executor, state=state)
        assert val == 2
        val = container.execute_sync(solved, executor=executor, state=state)
        assert val == 3


def test_test_caching_above_execution_scope_use_cache_true() -> None:
    values = iter(range(2))

    def dep() -> int:
        return next(values)

    container = Container()
    executor = SyncExecutor()
    solved = container.solve(Dependant(dep, scope="outer"), scopes=["outer", "inner"])

    with container.enter_scope("outer") as outer_state:
        with container.enter_scope("inner", state=outer_state) as inner_state:
            val = container.execute_sync(solved, executor=executor, state=inner_state)
            assert val == 0
            val = container.execute_sync(solved, executor=executor, state=inner_state)
            assert val == 0

        with container.enter_scope("inner", state=outer_state) as inner_state:
            val = container.execute_sync(solved, executor=executor, state=inner_state)
            assert val == 0
            val = container.execute_sync(solved, executor=executor, state=inner_state)
            assert val == 0

    with container.enter_scope("outer") as outer_state:
        with container.enter_scope("inner", state=outer_state) as inner_state:
            val = container.execute_sync(solved, executor=executor, state=inner_state)
            assert val == 1
            val = container.execute_sync(solved, executor=executor, state=inner_state)
            assert val == 1

        with container.enter_scope("inner", state=outer_state) as inner_state:
            val = container.execute_sync(solved, executor=executor, state=inner_state)
            assert val == 1
            val = container.execute_sync(solved, executor=executor, state=inner_state)
            assert val == 1


def test_test_caching_above_execution_scope_use_cache_false() -> None:
    values = iter(range(8))

    def dep() -> int:
        return next(values)

    container = Container()
    executor = SyncExecutor()
    solved = container.solve(
        Dependant(dep, scope="outer", use_cache=False), scopes=["outer", "inner"]
    )

    with container.enter_scope("outer") as outer_state:
        with container.enter_scope("inner", state=outer_state) as inner_state:
            val = container.execute_sync(solved, executor=executor, state=inner_state)
            assert val == 0
            val = container.execute_sync(solved, executor=executor, state=inner_state)
            assert val == 1

        with container.enter_scope("inner", state=outer_state) as inner_state:
            val = container.execute_sync(solved, executor=executor, state=inner_state)
            assert val == 2
            val = container.execute_sync(solved, executor=executor, state=inner_state)
            assert val == 3

    with container.enter_scope("outer") as outer_state:
        with container.enter_scope("inner", state=outer_state) as inner_state:
            val = container.execute_sync(solved, executor=executor, state=inner_state)
            assert val == 4
            val = container.execute_sync(solved, executor=executor, state=inner_state)
            assert val == 5

        with container.enter_scope("inner", state=outer_state) as inner_state:
            val = container.execute_sync(solved, executor=executor, state=inner_state)
            assert val == 6
            val = container.execute_sync(solved, executor=executor, state=inner_state)
            assert val == 7


def test_sharing_within_execution_scope() -> None:
    class Sentinel:
        pass

    def dep(
        one: Sentinel,
        two: Annotated[Sentinel, Marker(use_cache=False)],
        three: Sentinel,
    ) -> Tuple[Sentinel, Sentinel, Sentinel]:
        return (one, two, three)

    container = Container()
    executor = SyncExecutor()
    solved = container.solve(Dependant(dep), scopes=[None])
    with container.enter_scope(None) as state:
        one, two, three = container.execute_sync(solved, executor=executor, state=state)
        assert one is three
        assert two is not one


def test_dependant_custom_cache_key() -> None:

    # we make a dependant that does not care about the scope
    # so a "request" scoped dependency will pick up cache from an "app" scoped one
    class CustomDependant(Dependant[Any]):
        @property
        def cache_key(self) -> Any:
            return (self.__class__, self.call)

    @dataclass
    class State:
        foo: str = "bar"

    container = Container()
    app_scoped_state_dep = CustomDependant(State, scope="app")
    app_scoped_state_solved = container.solve(app_scoped_state_dep, scopes=["app"])
    request_scoped_state_dep = CustomDependant(State, scope="request")
    request_scoped_state_solved = container.solve(
        request_scoped_state_dep, scopes=["app", "request"]
    )

    with container.enter_scope("app") as app_state:
        instance_1 = container.execute_sync(
            app_scoped_state_solved, executor=SyncExecutor(), state=app_state
        )
        with container.enter_scope("request", state=app_state) as request_state:
            instance_2 = container.execute_sync(
                request_scoped_state_solved,
                executor=SyncExecutor(),
                state=request_state,
            )

        assert instance_2 is instance_1
