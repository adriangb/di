from typing import Tuple

import pytest

from di import Container, Dependant, Depends


class Request:
    def __init__(self, value: int = 0) -> None:
        self.value = value


def endpoint(r: Request) -> int:
    return r.value


def test_bind():
    container = Container()
    with container.enter_global_scope("app"):
        r = container.execute_sync(container.solve(Dependant(endpoint)))
        assert r == 0  # just the default value
        with container.enter_local_scope("request"):
            request = Request(1)  # build a request
            # bind the request
            with container.bind(Dependant(lambda: request), Request):
                r = container.execute_sync(container.solve(Dependant(endpoint)))
                assert r == 1  # bound value
                with container.bind(Dependant(lambda: Request(2)), Request):
                    r = container.execute_sync(container.solve(Dependant(endpoint)))
                    assert r == 2
                r = container.execute_sync(container.solve(Dependant(endpoint)))
                assert r == 1
        # when we exit the request scope, the bind of value=1 gets cleared
        r = container.execute_sync(container.solve(Dependant(endpoint)))
        assert r == 0  # back to the default value


def inject1() -> int:
    return 1  # pragma: no cover


def inject2() -> int:
    return 2  # pragma: no cover


def inject3() -> int:
    return 3  # pragma: no cover


async def endpoint2(
    v1: int = Depends(inject1), v2: int = Depends(inject2), v3: int = Depends(inject3)
) -> Tuple[int, int, int]:
    return v1, v2, v3


async def run_endpoint2(expected: Tuple[int, int, int], container: Container):
    async with container.enter_local_scope("request"):
        with container.bind(Dependant(lambda: expected[2]), inject3):
            got = await container.execute_async(container.solve(Dependant(endpoint2)))
    assert expected == got, (expected, got)


def raises_exception() -> None:
    raise ValueError


def transitive(_: None = Depends(raises_exception)) -> None:
    ...


def dep(t: None = Depends(transitive)) -> None:
    ...


def test_bind_transitive_dependency_results_skips_subdpendencies():
    """If we bind a transitive dependency none of it's sub-dependencies should be executed
    since they are no longer required.
    """
    container = Container()
    with container.enter_global_scope("something"):
        # we get an error from raises_exception
        with pytest.raises(ValueError):
            container.execute_sync(container.solve(Dependant(dep)))

        # we bind a non-error provider and re-execute, now raises_exception
        # should not execute at all

        def not_error() -> None:
            ...

        with container.bind(Dependant(not_error), transitive):
            container.execute_sync(container.solve(Dependant(dep)))
        # and this reverts when the bind exits
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

    container = Container()
    with container.enter_global_scope("something"):
        assert (container.execute_sync(container.solve(Dependant(return_four)))) == 4
        with container.bind(Dependant(return_three), return_two):
            assert (
                container.execute_sync(container.solve(Dependant(return_four)))
            ) == 5
