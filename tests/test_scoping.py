import contextlib
import typing

import anyio
import pytest

from di import Container, Dependant, SyncExecutor
from di.api.scopes import Scope
from di.exceptions import DuplicateScopeError
from di.typing import Annotated


class Dep:
    def __init__(self) -> None:
        self.value: int = 0

    def __call__(self) -> int:
        return self.value


dep1 = Dep()
dep2 = Dep()


def use_cache(v: Annotated[int, Dependant(dep1, scope="scope")]):
    return v


def not_use_cache(v: Annotated[int, Dependant(dep1, scope="scope", use_cache=False)]):
    return v


def test_scoped_execute():
    container = Container(scopes=("scope", None))
    use_cache_solved = container.solve(Dependant(use_cache))
    not_use_cache_solved = container.solve(Dependant(not_use_cache))
    with container.enter_scope("scope"):
        dep1.value = 1
        with container.enter_scope(None):
            r = container.execute_sync(use_cache_solved, executor=SyncExecutor())
        assert r == 1, r
        # we change the value to 2, but we should still get back 1
        # since the value is cached
        dep1.value = 2
        with container.enter_scope(None):
            r = container.execute_sync(use_cache_solved, executor=SyncExecutor())
        assert r == 1, r
        # but if we execute a non-use_cache dependency, we get the current value
        with container.enter_scope(None):
            r = container.execute_sync(not_use_cache_solved, executor=SyncExecutor())
        assert r == 2, r
    with container.enter_scope("scope"):
        # now that we exited and re-entered the scope the cache was cleared
        with container.enter_scope(None):
            r = container.execute_sync(use_cache_solved, executor=SyncExecutor())
        assert r == 2, r


@pytest.mark.parametrize("outer", ("global", "local"))
@pytest.mark.parametrize("inner", ("global", "local"))
def test_duplicate_global_scope(outer: Scope, inner: Scope):
    """Cannot enter the same global scope twice"""

    container = Container(scopes=(None,))

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

    DepA = Dependant(A, scope="app")

    def B(a: Annotated[str, DepA]) -> str:
        return a + holder[1]

    DepB = Dependant(B, scope="request")

    def C(b: Annotated[str, DepB]) -> str:
        return b + holder[2]

    DepC = Dependant(C, scope="request")

    def endpoint(c: Annotated[str, DepC]) -> str:
        return c

    DepEndpoint = Dependant(endpoint, scope="request")

    container = Container(scopes=("app", "request", "endpoint"))
    with container.enter_scope("app"):
        with container.enter_scope("request"):
            res = container.execute_sync(
                container.solve(DepEndpoint), executor=SyncExecutor()
            )
            assert res == "ABC"
            # values should be cached as long as we're within the request scope
            holder[:] = "DEF"
            with container.enter_scope("endpoint"):
                assert (
                    container.execute_sync(
                        container.solve(DepEndpoint), executor=SyncExecutor()
                    )
                ) == "ABC"
            with container.enter_scope("endpoint"):
                assert (
                    container.execute_sync(
                        container.solve(DepC), executor=SyncExecutor()
                    )
                ) == "ABC"
            with container.enter_scope("endpoint"):
                assert (
                    container.execute_sync(
                        container.solve(DepB), executor=SyncExecutor()
                    )
                ) == "AB"
            with container.enter_scope("endpoint"):
                assert (
                    container.execute_sync(
                        container.solve(DepA), executor=SyncExecutor()
                    )
                ) == "A"
        # A is still cached because it is lifespan scoped
        assert (
            container.execute_sync(container.solve(DepA), executor=SyncExecutor())
        ) == "A"


def test_nested_lifecycle():

    state: typing.Dict[str, str] = dict.fromkeys(("A", "B", "C"), "uninitialized")

    @contextlib.contextmanager
    def A() -> typing.Generator[None, None, None]:
        state["A"] = "initialized"
        yield
        state["A"] = "destroyed"

    @contextlib.contextmanager
    def B(
        a: Annotated[None, Dependant(A, scope="lifespan")]
    ) -> typing.Generator[None, None, None]:
        state["B"] = "initialized"
        yield
        state["B"] = "destroyed"

    @contextlib.contextmanager
    def C(
        b: Annotated[None, Dependant(B, scope="request")]
    ) -> typing.Generator[None, None, None]:
        state["C"] = "initialized"
        yield
        state["C"] = "destroyed"

    def endpoint(c: Annotated[None, Dependant(C, scope="request")]) -> None:
        return

    container = Container(scopes=("lifespan", "request", "endpoint"))
    with container.enter_scope("lifespan"):
        with container.enter_scope("request"):
            assert list(state.values()) == ["uninitialized"] * 3
            with container.enter_scope("endpoint"):
                container.execute_sync(
                    container.solve(Dependant(endpoint, scope="endpoint")),
                    executor=SyncExecutor(),
                )
            assert list(state.values()) == ["initialized"] * 3
        assert list(state.values()) == ["initialized", "destroyed", "destroyed"]
    assert list(state.values()) == ["destroyed", "destroyed", "destroyed"]


@pytest.mark.anyio
async def test_enter_scope_concurrently():
    """We can enter the same scope from two different concurrent tasks"""

    container = Container(scopes=("request",))

    async def endpoint() -> None:
        async with container.enter_scope("request"):
            await anyio.sleep(
                0.05  # make sure execution overlaps, the number is arbitrary
            )

    async with anyio.create_task_group() as tg:
        tg.start_soon(endpoint)
        tg.start_soon(endpoint)
