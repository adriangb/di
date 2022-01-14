import typing

import anyio
import pytest
from typing_extensions import Annotated

from di import Container, Dependant, Depends
from di.api.scopes import Scope
from di.exceptions import DuplicateScopeError, UnknownScopeError


class Dep:
    def __init__(self) -> None:
        self.value: int = 0

    def __call__(self) -> int:
        return self.value


dep1 = Dep()
dep2 = Dep()


def share(v: int = Depends(dep1, scope="app")):
    return v


def not_share(v: int = Depends(dep1, scope="app", share=False)):
    return v


def test_scoped_execute():
    container = Container()
    with container.enter_scope("app"):
        dep1.value = 1
        r = container.execute_sync(container.solve(Dependant(share)))
        assert r == 1, r
        # we change the value to 2, but we should still get back 1
        # since the value is cached
        dep1.value = 2
        r = container.execute_sync(container.solve(Dependant(share)))
        assert r == 1, r
        # but if we execute a non-share dependency, we get the current value
        r = container.execute_sync(container.solve(Dependant(not_share)))
        assert r == 2, r
    with container.enter_scope("app"):
        # now that we exited and re-entered app scope the cache was cleared
        r = container.execute_sync(container.solve(Dependant(share)))
        assert r == 2, r


def test_unknown_scope():
    def bad_dep(v: int = Depends(dep1, scope="abcde")) -> int:
        return v

    container = Container()
    with container.enter_scope("app"):
        with pytest.raises(UnknownScopeError):
            container.execute_sync(container.solve(Dependant(bad_dep)))


@pytest.mark.parametrize("outer", ("global", "local"))
@pytest.mark.parametrize("inner", ("global", "local"))
def test_duplicate_global_scope(outer: Scope, inner: Scope):
    """Cannot enter the same global scope twice"""

    container = Container()

    fn = {
        typing.cast(Scope, "global"): container.enter_scope,
        typing.cast(Scope, "local"): container.enter_scope,
    }

    with fn[outer]("app"):
        with pytest.raises(DuplicateScopeError):
            with fn[inner]("app"):
                ...


def test_nested_caching():

    holder: typing.List[str] = ["A", "B", "C"]

    def A() -> str:
        return holder[0]

    DepA = Dependant(A, scope="lifespan")

    def B(a: Annotated[str, DepA]) -> str:
        return a + holder[1]

    DepB = Dependant(B, scope="request")

    def C(b: Annotated[str, DepB]) -> str:
        return b + holder[2]

    DepC = Dependant(C, scope="request")

    def endpoint(c: Annotated[str, DepC]) -> str:
        return c

    DepEndpoint = Dependant(endpoint, scope="request")

    container = Container()
    with container.enter_scope("lifespan"):
        with container.enter_scope("request"):
            res = container.execute_sync(container.solve(DepEndpoint))
            assert res == "ABC"
            # values should be cached as long as we're within the request scope
            holder[:] = "DEF"
            assert (container.execute_sync(container.solve(DepEndpoint))) == "ABC"
            assert (container.execute_sync(container.solve(DepC))) == "ABC"
            assert (container.execute_sync(container.solve(DepB))) == "AB"
            assert (container.execute_sync(container.solve(DepA))) == "A"
        # A is still cached for B because it is lifespan scoped
        assert (container.execute_sync(container.solve(Dependant(B)))) == "AE"


def test_nested_lifecycle():

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
    with container.enter_scope("lifespan"):
        with container.enter_scope("request"):
            assert list(state.values()) == ["uninitialized"] * 3
            container.execute_sync(container.solve(Dependant(endpoint)))
            assert list(state.values()) == ["initialized"] * 3
        assert list(state.values()) == ["initialized", "destroyed", "destroyed"]
    assert list(state.values()) == ["destroyed", "destroyed", "destroyed"]


@pytest.mark.anyio
async def test_concurrent_local_scopes():
    """We can enter the same local scope from two different concurrent tasks"""

    container = Container()

    async def endpoint() -> None:
        async with container.enter_scope("request"):
            await anyio.sleep(
                0.05  # make sure execution overlaps, the number is arbitrary
            )

    async with anyio.create_task_group() as tg:
        tg.start_soon(endpoint)
        tg.start_soon(endpoint)


@pytest.mark.anyio
async def test_execution_scope_already_entered():
    """Container allows us to manually enter the default scope"""

    container = Container(execution_scope=None)

    def dep() -> None:
        ...

    async with container.enter_scope(None):
        await container.execute_async(container.solve(Dependant(dep)))
        container.execute_sync(container.solve(Dependant(dep)))

    with container.enter_scope(None):
        container.execute_sync(container.solve(Dependant(dep)))
