import pytest

from di import Container, Dependant, Depends


class Request:
    def __init__(self, value: int = 0) -> None:
        self.value = value


def endpoint(r: Request) -> int:
    return r.value


def test_bind():
    container = Container(scopes=(None,))

    def func() -> int:
        return 1

    dependant = Dependant(func)

    with container.enter_scope(None):
        res = container.execute_sync(container.solve(dependant))
        assert res == 1
    with container.bind(Dependant(lambda: 2), func):
        with container.enter_scope(None):
            res = container.execute_sync(container.solve(dependant))
            assert res == 2
    with container.enter_scope(None):
        res = container.execute_sync(container.solve(dependant))
        assert res == 1


def test_bind_transitive_dependency_results_skips_subdpendencies():
    """If we bind a transitive dependency none of it's sub-dependencies should be executed
    since they are no longer required.
    """

    def raises_exception() -> None:
        raise ValueError

    def transitive(_: None = Depends(raises_exception)) -> None:
        ...

    def dep(t: None = Depends(transitive)) -> None:
        ...

    container = Container(scopes=(None,))
    with container.enter_scope(None):
        # we get an error from raises_exception
        with pytest.raises(ValueError):
            container.execute_sync(container.solve(Dependant(dep)))

    # we bind a non-error provider and re-execute, now raises_exception
    # should not execute at all

    def not_error() -> None:
        ...

    with container.bind(Dependant(not_error), transitive):
        with container.enter_scope(None):
            container.execute_sync(container.solve(Dependant(dep)))
    # and this reverts when the bind exits
    with container.enter_scope(None):
        with pytest.raises(ValueError):
            container.execute_sync(container.solve(Dependant(dep)))


def test_bind_with_dependencies():
    """When we bind a new dependant, we resolve it's dependencies as well"""

    def return_one() -> int:
        return 1

    def return_two(one: int = Depends(return_one)) -> int:
        return one + 1

    def return_three(one: int = Depends(return_one)) -> int:
        return one + 2

    def return_four(two: int = Depends(return_two)) -> int:
        return two + 2

    container = Container(scopes=(None,))
    with container.enter_scope(None):
        assert (container.execute_sync(container.solve(Dependant(return_four)))) == 4
    with container.bind(Dependant(return_three), return_two):
        with container.enter_scope(None):
            val = container.execute_sync(container.solve(Dependant(return_four)))
        assert val == 5
