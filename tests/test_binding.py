from typing import List

import pytest

from di import Container, Dependant, SyncExecutor
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

    dependant = Dependant(Test)

    with container.enter_scope(None):
        res = container.execute_sync(
            container.solve(dependant), executor=SyncExecutor()
        )
        assert res.v == 1
    with container.bind_by_type(Dependant(lambda: Test(2)), Test):
        with container.enter_scope(None):
            res = container.execute_sync(
                container.solve(dependant), executor=SyncExecutor()
            )
            assert res.v == 2
    with container.enter_scope(None):
        res = container.execute_sync(
            container.solve(dependant), executor=SyncExecutor()
        )
        assert res.v == 1


def test_bind_transitive_dependency_results_skips_subdpendencies():
    """If we bind a transitive dependency none of it's sub-dependencies should be executed
    since they are no longer required.
    """

    def raises_exception() -> None:
        raise ValueError

    def transitive(_: Annotated[None, Dependant(raises_exception)]) -> None:
        ...

    def dep(t: Annotated[None, Dependant(transitive)]) -> None:
        ...

    container = Container()
    with container.enter_scope(None):
        # we get an error from raises_exception
        with pytest.raises(ValueError):
            container.execute_sync(
                container.solve(Dependant(dep)), executor=SyncExecutor()
            )

    # we bind a non-error provider and re-execute, now raises_exception
    # should not execute at all

    def not_error() -> None:
        ...

    with container.bind_by_type(Dependant(not_error), transitive):
        with container.enter_scope(None):
            container.execute_sync(
                container.solve(Dependant(dep)), executor=SyncExecutor()
            )
    # and this reverts when the bind exits
    with container.enter_scope(None):
        with pytest.raises(ValueError):
            container.execute_sync(
                container.solve(Dependant(dep)), executor=SyncExecutor()
            )


def test_bind_with_dependencies():
    """When we bind a new dependant, we resolve it's dependencies as well"""

    def return_one() -> int:
        return 1

    def return_two(one: Annotated[int, Dependant(return_one)]) -> int:
        return one + 1

    def return_three(one: Annotated[int, Dependant(return_one)]) -> int:
        return one + 2

    def return_four(two: Annotated[int, Dependant(return_two)]) -> int:
        return two + 2

    container = Container()
    with container.enter_scope(None):
        assert (
            container.execute_sync(
                container.solve(Dependant(return_four)), executor=SyncExecutor()
            )
        ) == 4
    container.register_bind_hook(
        lambda param, dependant: None
        if dependant.call is not return_two
        else Dependant(return_three)
    )
    with container.enter_scope(None):
        val = container.execute_sync(
            container.solve(Dependant(return_four)), executor=SyncExecutor()
        )
    assert val == 5


def test_bind_covariant() -> None:
    class Animal:
        pass

    class Dog(Animal):
        pass

    container = Container()
    container.bind_by_type(
        Dependant(lambda: Dog()),
        Animal,
        covariant=True,
    )

    # include a generic to make sure we are safe with
    # isisntance checks and MRO checks
    def dep(animal: Animal, generic: Annotated[List[int], Dependant(list)]) -> Animal:
        return animal

    solved = container.solve(Dependant(dep))

    with container.enter_scope(None):
        instance = container.execute_sync(solved, executor=SyncExecutor())

    assert isinstance(instance, Dog)
