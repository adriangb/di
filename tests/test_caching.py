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
    solved = container.solve(Dependant(dep))

    with container.enter_scope(None):
        val = container.execute_sync(solved, executor=executor)
        assert val == 0
        val = container.execute_sync(solved, executor=executor)
        assert val == 0

    with container.enter_scope(None):
        val = container.execute_sync(solved, executor=executor)
        assert val == 1
        val = container.execute_sync(solved, executor=executor)
        assert val == 1


def test_test_caching_within_execution_scope_use_cache_false() -> None:
    values = iter(range(4))

    def dep() -> int:
        return next(values)

    container = Container()
    executor = SyncExecutor()
    solved = container.solve(Dependant(dep, use_cache=False))

    with container.enter_scope(None):
        val = container.execute_sync(solved, executor=executor)
        assert val == 0
        val = container.execute_sync(solved, executor=executor)
        assert val == 1

    with container.enter_scope(None):
        val = container.execute_sync(solved, executor=executor)
        assert val == 2
        val = container.execute_sync(solved, executor=executor)
        assert val == 3


def test_test_caching_above_execution_scope_use_cache_true() -> None:
    values = iter(range(2))

    def dep() -> int:
        return next(values)

    container = Container(scopes=("outer", "inner"))
    executor = SyncExecutor()
    solved = container.solve(Dependant(dep, scope="outer"))

    with container.enter_scope("outer"):
        with container.enter_scope("inner"):
            val = container.execute_sync(solved, executor=executor)
            assert val == 0
            val = container.execute_sync(solved, executor=executor)
            assert val == 0

        with container.enter_scope("inner"):
            val = container.execute_sync(solved, executor=executor)
            assert val == 0
            val = container.execute_sync(solved, executor=executor)
            assert val == 0

    with container.enter_scope("outer"):
        with container.enter_scope("inner"):
            val = container.execute_sync(solved, executor=executor)
            assert val == 1
            val = container.execute_sync(solved, executor=executor)
            assert val == 1

        with container.enter_scope("inner"):
            val = container.execute_sync(solved, executor=executor)
            assert val == 1
            val = container.execute_sync(solved, executor=executor)
            assert val == 1


def test_test_caching_above_execution_scope_use_cache_false() -> None:
    values = iter(range(8))

    def dep() -> int:
        return next(values)

    container = Container(scopes=("outer", "inner"))
    executor = SyncExecutor()
    solved = container.solve(Dependant(dep, scope="outer", use_cache=False))

    with container.enter_scope("outer"):
        with container.enter_scope("inner"):
            val = container.execute_sync(solved, executor=executor)
            assert val == 0
            val = container.execute_sync(solved, executor=executor)
            assert val == 1

        with container.enter_scope("inner"):
            val = container.execute_sync(solved, executor=executor)
            assert val == 2
            val = container.execute_sync(solved, executor=executor)
            assert val == 3

    with container.enter_scope("outer"):
        with container.enter_scope("inner"):
            val = container.execute_sync(solved, executor=executor)
            assert val == 4
            val = container.execute_sync(solved, executor=executor)
            assert val == 5

        with container.enter_scope("inner"):
            val = container.execute_sync(solved, executor=executor)
            assert val == 6
            val = container.execute_sync(solved, executor=executor)
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
    solved = container.solve(Dependant(dep))
    with container.enter_scope(None):
        one, two, three = container.execute_sync(solved, executor=executor)
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

    container = Container(scopes=("app", "request"))
    app_scoped_state_dep = CustomDependant(State, scope="app")
    app_scoped_state_solved = container.solve(app_scoped_state_dep)
    request_scoped_state_dep = CustomDependant(State, scope="request")
    request_scoped_state_solved = container.solve(request_scoped_state_dep)

    with container.enter_scope("app"):
        instance_1 = container.execute_sync(
            app_scoped_state_solved, executor=SyncExecutor()
        )
        with container.enter_scope("request"):
            instance_2 = container.execute_sync(
                request_scoped_state_solved, executor=SyncExecutor()
            )

        assert instance_2 is instance_1
