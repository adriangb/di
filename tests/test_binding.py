from typing import List

import pytest

from di.container import Container, bind_by_type
from di.dependent import Dependent, Marker
from di.executors import SyncExecutor
from di.typing import Annotated


class Request:
    def __init__(self, value: int = 0) -> None:
        self.value = value


def endpoint(r: Request) -> int:
    return r.value


def test_bind():
    container = Container()

    class Test:
        def __init__(self, v: int = 1) -> None:
            self.v = v

    dependent = Dependent(Test)

    with container.enter_scope(None) as state:
        res = container.execute_sync(
            container.solve(dependent, scopes=[None]),
            executor=SyncExecutor(),
            state=state,
        )
        assert res.v == 1
    with container.bind(bind_by_type(Dependent(lambda: Test(2)), Test)):
        with container.enter_scope(None) as state:
            res = container.execute_sync(
                container.solve(dependent, scopes=[None]),
                executor=SyncExecutor(),
                state=state,
            )
            assert res.v == 2
    with container.enter_scope(None) as state:
        res = container.execute_sync(
            container.solve(dependent, scopes=[None]),
            executor=SyncExecutor(),
            state=state,
        )
        assert res.v == 1


def test_bind_transitive_dependency_results_skips_subdpendencies():
    """If we bind a transitive dependency none of it's sub-dependencies should be executed
    since they are no longer required.
    """

    def raises_exception() -> None:
        raise ValueError

    class Transitive:
        def __init__(self, _: Annotated[None, Marker(raises_exception)]) -> None:
            ...

    def dep(t: Annotated[None, Marker(Transitive)]) -> None:
        ...

    container = Container()
    with container.enter_scope(None) as state:
        # we get an error from raises_exception
        with pytest.raises(ValueError):
            container.execute_sync(
                container.solve(Dependent(dep), scopes=[None]),
                executor=SyncExecutor(),
                state=state,
            )

    # we bind a non-error provider and re-execute, now raises_exception
    # should not execute at all

    def not_error() -> None:
        ...

    with container.bind(bind_by_type(Dependent(not_error), Transitive)):
        with container.enter_scope(None) as state:
            container.execute_sync(
                container.solve(Dependent(dep), scopes=[None]),
                executor=SyncExecutor(),
                state=state,
            )
    # and this reverts when the bind exits
    with container.enter_scope(None) as state:
        with pytest.raises(ValueError):
            container.execute_sync(
                container.solve(Dependent(dep), scopes=[None]),
                executor=SyncExecutor(),
                state=state,
            )


def test_bind_with_dependencies():
    """When we bind a new dependent, we resolve it's dependencies as well"""

    def return_one() -> int:
        return 1

    def return_two(one: Annotated[int, Marker(return_one)]) -> int:
        return one + 1

    def return_three(one: Annotated[int, Marker(return_one)]) -> int:
        return one + 2

    def return_four(two: Annotated[int, Marker(return_two)]) -> int:
        return two + 2

    container = Container()
    with container.enter_scope(None) as state:
        assert (
            container.execute_sync(
                container.solve(Dependent(return_four), scopes=[None]),
                executor=SyncExecutor(),
                state=state,
            )
        ) == 4
    container.bind(
        lambda param, dependent: None
        if dependent.call is not return_two
        else Dependent(return_three)
    )
    with container.enter_scope(None) as state:
        val = container.execute_sync(
            container.solve(Dependent(return_four), scopes=[None]),
            executor=SyncExecutor(),
            state=state,
        )
    assert val == 5


def test_bind_covariant() -> None:
    class Animal:
        pass

    class Dog(Animal):
        pass

    container = Container()
    container.bind(
        bind_by_type(
            Dependent(lambda: Dog()),
            Animal,
            covariant=True,
        )
    )

    # include a generic to make sure we are safe with
    # isisntance checks and MRO checks
    def dep(animal: Animal, generic: Annotated[List[int], Marker(list)]) -> Animal:
        return animal

    solved = container.solve(Dependent(dep), scopes=[None])

    with container.enter_scope(None) as state:
        instance = container.execute_sync(solved, executor=SyncExecutor(), state=state)

    assert isinstance(instance, Dog)
