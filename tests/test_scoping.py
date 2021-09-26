import typing

import anyio
import pytest

from di.container import Container
from di.dependency import Dependant, Scope
from di.exceptions import DuplicateScopeError, UnknownScopeError
from di.params import Depends


class Dep:
    def __init__(self) -> None:
        self.value: int = 0

    def __call__(self) -> int:
        return self.value


dep1 = Dep()
dep2 = Dep()


def app_scoped(v: int = Depends(dep1, scope="app")):
    return v


def request_scoped(v: int = Depends(dep1, scope="request")):
    return v


def not_shared(v: int = Depends(dep1, scope=None, shared=False)):
    return v


def default_scope(v: int = Depends(dep1)):
    return v


@pytest.mark.anyio
async def test_scoped_execute():
    container = Container()
    async with container.enter_global_scope("app"):
        dep1.value = 1
        r = await container.execute(Dependant(app_scoped))
        assert r == 1, r
        # we change the value to 2, but we should still get back 1
        # since the value is cached
        dep1.value = 2
        r = await container.execute(Dependant(app_scoped))
        assert r == 1, r
        # but if we execute a non-shared dependency, we get the current value
        r = await container.execute(Dependant(not_shared))
        assert r == 2, r
        # the default scope is None, which gives us the value cached
        # in the app scope since the app scope is outside of the None scope
        r = await container.execute(Dependant(default_scope))
        assert r == 1, r
    # now that we exited the app scope the cache was cleared
    # and so the default scope gives us the new value
    r = await container.execute(Dependant(default_scope))
    assert r == 2, r
    # and it gets refreshed every call to execute()
    dep1.value = 3
    r = await container.execute(Dependant(default_scope))
    assert r == 3, r


@pytest.mark.anyio
async def test_unknown_scope():
    def bad_dep(v: int = Depends(dep1, scope="abcde")) -> int:
        return v

    container = Container()
    async with container.enter_global_scope("app"):
        with pytest.raises(UnknownScopeError):
            await container.execute(Dependant(bad_dep))


@pytest.mark.anyio
@pytest.mark.parametrize("outer", ("global", "local"))
@pytest.mark.parametrize("inner", ("global", "local"))
async def test_duplicate_global_scope(outer: Scope, inner: Scope):
    """Cannot enter the same global scope twice"""

    container = Container()

    fn: typing.Dict[
        Scope, typing.Callable[[Scope], typing.AsyncContextManager[None]]
    ] = {
        "global": container.enter_global_scope,
        "local": container.enter_local_scope,
    }  # type: ignore

    async with fn[outer]("app"):
        with pytest.raises(DuplicateScopeError):
            async with fn[inner]("app"):
                ...


@pytest.mark.anyio
async def test_nested_caching():

    holder: typing.List[str] = ["A", "B", "C"]

    def A() -> str:
        return holder[0]

    def B(a: str = Depends(A, scope="lifespan")) -> str:
        return a + holder[1]

    def C(b: str = Depends(B, scope="request")) -> str:
        return b + holder[2]

    def endpoint(c: str = Depends(C, scope="request")) -> str:
        return c

    container = Container()
    async with container.enter_local_scope("lifespan"):
        async with container.enter_local_scope("request"):
            res = await container.execute(Dependant(endpoint))
            assert res == "ABC"
            # values should be cached as long as we're within the request scope
            holder[:] = "DEF"
            assert (await container.execute(Dependant(endpoint))) == "ABC"
            assert (await container.execute(Dependant(C))) == "ABC"
            assert (await container.execute(Dependant(B))) == "AB"
            assert (await container.execute(Dependant(A))) == "A"
        # A is still cached for B because it is lifespan scoped
        assert (await container.execute(Dependant(B))) == "AE"


@pytest.mark.anyio
async def test_nested_lifecycle():

    state: typing.Dict[str, str] = dict.fromkeys(("A", "B", "C"), "uninitialized")

    def A() -> typing.Generator[None, None, None]:
        state["A"] = "initialized"
        yield
        state["A"] = "destroyed"

    def B(a: None = Depends(A, scope="lifespan")) -> typing.Generator[None, None, None]:
        state["B"] = "initialized"
        yield
        state["B"] = "destroyed"

    def C(b: None = Depends(B, scope="request")) -> typing.Generator[None, None, None]:
        state["C"] = "initialized"
        yield
        state["C"] = "destroyed"

    def endpoint(c: None = Depends(C, scope="request")) -> None:
        return

    container = Container()
    async with container.enter_local_scope("lifespan"):
        async with container.enter_local_scope("request"):
            assert list(state.values()) == ["uninitialized"] * 3
            await container.execute(Dependant(endpoint))
            assert list(state.values()) == ["initialized"] * 3
        assert list(state.values()) == ["initialized", "destroyed", "destroyed"]
    assert list(state.values()) == ["destroyed", "destroyed", "destroyed"]


@pytest.mark.anyio
async def test_concurrent_local_scopes():
    """We can enter the same local scope from two different concurrent tasks"""

    container = Container()

    async def endpoint() -> None:
        async with container.enter_local_scope("request"):
            await anyio.sleep(
                0.05
            )  # make sure execution overlaps, the number is arbitrary

    async with anyio.create_task_group() as tg:
        tg.start_soon(endpoint)  # type: ignore
        tg.start_soon(endpoint)  # type: ignore
