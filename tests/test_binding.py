from typing import Tuple

import anyio
import pytest

from di.container import Container
from di.dependency import Dependant
from di.params import Depends


class Request:
    def __init__(self, value: int = 0) -> None:
        self.value = value


def endpoint(r: Request) -> int:
    return r.value


@pytest.mark.anyio
async def test_bind():
    container = Container()
    async with container.enter_global_scope("app"):
        r = await container.execute(Dependant(endpoint))
        assert r == 0  # just the default value
        async with container.enter_local_scope("request"):
            request = Request(1)  # build a request
            # bind the request
            container.bind(Dependant(lambda: request), Request, scope="request")
            r = await container.execute(Dependant(endpoint))
            assert r == 1  # bound value
            with container.bind(
                Dependant(lambda: Request(2)), Request, scope="request"
            ):
                r = await container.execute(Dependant(endpoint))
                assert r == 2
            r = await container.execute(Dependant(endpoint))
            assert r == 1
        # when we exit the request scope, the bind of value=1 gets cleared
        r = await container.execute(Dependant(endpoint))
        assert r == 0  # back to the default value


def inject1():
    return -1


def inject2():
    return -2


def inject3():
    return -2


async def endpoint2(
    v1: int = Depends(inject1), v2: int = Depends(inject2), v3: int = Depends(inject3)
) -> Tuple[int, int, int]:
    return v1, v2, v3


async def run_endpoint2(expected: Tuple[int, int, int], container: Container):
    async with container.enter_local_scope("request"):
        container.bind(Dependant(lambda: expected[2]), inject3, scope="request")
        got = await container.execute(Dependant(endpoint2))
    assert expected == got, (expected, got)


@pytest.mark.anyio
async def test_concurrent_binds():
    """We can bind different values at the same time as long as we are within
    different local scopes
    """
    container = Container()
    async with container.enter_local_scope("app-local"):
        container.bind(Dependant(lambda: -10), inject1, scope="app-local")
        async with container.enter_global_scope("app-global"):
            container.bind(Dependant(lambda: -20), inject2, scope="app-global")
            async with anyio.create_task_group() as tg:
                for i in range(10):
                    tg.start_soon(run_endpoint2, (-10, -20, i), container)  # type: ignore


async def return_zero() -> int:
    return 0


async def bind(container: Container) -> None:
    container.bind(Dependant(lambda: 10), return_zero, scope="something")


async def return_one(zero: int = Depends(return_zero)) -> int:
    return zero + 1


@pytest.mark.anyio
async def test_bind_within_execution():
    container = Container()
    async with container.enter_global_scope("something"):
        await container.execute(Dependant(bind))
        res = await container.execute(Dependant(return_one))
        assert res == 11
    # the bind persists even after we exit the "something" scope
    #
    res = await container.execute(Dependant(return_one))
    assert res == 11


def raises_exception() -> None:
    raise ValueError


def transitive(_: None = Depends(raises_exception)) -> None:
    ...


def dep(t: None = Depends(transitive)) -> None:
    ...


@pytest.mark.anyio
async def test_bind_transitive_dependency_results_skips_subdpendencies():
    """If we bind a transitive dependency none of it's sub-dependencies should be executed
    since they are no longer required.
    """
    container = Container()
    async with container.enter_global_scope("something"):
        # we get an error from raises_exception
        with pytest.raises(ValueError):
            await container.execute(Dependant(dep))

        # we bind a non-error provider and re-execute, now raises_exception
        # should not execute at all

        def not_error() -> None:
            ...

        with container.bind(Dependant(not_error), transitive, scope="something"):
            await container.execute(Dependant(dep))
        # and this reverts when the bind exits
        with pytest.raises(ValueError):
            await container.execute(Dependant(dep))


@pytest.mark.anyio
async def test_bind_with_dependencies():
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
    async with container.enter_global_scope("something"):
        assert (await container.execute(Dependant(return_four))) == 4
        with container.bind(Dependant(return_three), return_two, scope="something"):
            assert (await container.execute(Dependant(return_four))) == 5
