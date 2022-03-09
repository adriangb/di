import typing

import anyio
import pytest

from di.container import Container
from di.dependant import Dependant, Marker
from di.exceptions import DuplicateScopeError
from di.executors import SyncExecutor
from di.typing import Annotated


class Dep:
    def __init__(self) -> None:
        self.value: int = 0

    def __call__(self) -> int:
        return self.value


dep1 = Dep()
dep2 = Dep()


def use_cache(v: Annotated[int, Marker(dep1, scope="outer")]):
    return v


def not_use_cache(v: Annotated[int, Marker(dep1, scope="outer", use_cache=False)]):
    return v


def test_scoped_execute():
    container = Container()
    use_cache_solved = container.solve(Dependant(use_cache), scopes=["outer", "inner"])
    not_use_cache_solved = container.solve(
        Dependant(not_use_cache), scopes=["outer", "inner"]
    )
    with container.enter_scope("outer") as outer_state:
        dep1.value = 1
        with container.enter_scope(None, state=outer_state) as state:
            r = container.execute_sync(
                use_cache_solved, executor=SyncExecutor(), state=state
            )
        assert r == 1, r
        # we change the value to 2, but we should still get back 1
        # since the value is cached
        dep1.value = 2
        with container.enter_scope(None, state=outer_state) as state:
            r = container.execute_sync(
                use_cache_solved, executor=SyncExecutor(), state=state
            )
        assert r == 1, r
        # but if we execute a non-use_cache dependency, we get the current value
        with container.enter_scope(None, state=outer_state) as state:
            r = container.execute_sync(
                not_use_cache_solved, executor=SyncExecutor(), state=state
            )
        assert r == 2, r
    with container.enter_scope("outer") as outer_state:
        # now that we exited and re-entered the scope the cache was cleared
        with container.enter_scope(None, state=outer_state) as state:
            r = container.execute_sync(
                use_cache_solved, executor=SyncExecutor(), state=state
            )
        assert r == 2, r


@pytest.mark.parametrize("outer", ("global", "local"))
@pytest.mark.parametrize("inner", ("global", "local"))
def test_duplicate_global_scope(outer: str, inner: str):
    """Cannot enter the same scope twice"""

    container = Container()

    with container.enter_scope("app") as outer_state:
        with pytest.raises(DuplicateScopeError):
            with container.enter_scope("app", state=outer_state):
                ...


def test_nested_caching():

    holder: typing.List[str] = ["A", "B", "C"]

    def A() -> str:
        return holder[0]

    MarkerA = Marker(A, scope="app")
    DepA = Dependant(A, scope="request")

    def B(a: Annotated[str, MarkerA]) -> str:
        return a + holder[1]

    MarkerB = Marker(B, scope="request")
    DepB = Dependant(B, scope="request")

    def C(b: Annotated[str, MarkerB]) -> str:
        return b + holder[2]

    MarkerC = Marker(C, scope="request")
    DepC = Dependant(C, scope="request")

    def endpoint(c: Annotated[str, MarkerC]) -> str:
        return c

    DepEndpoint = Dependant(endpoint, scope="request")

    container = Container()
    scopes = ["app", "request", "endpoint"]
    endpoint_solved = container.solve(DepEndpoint, scopes=scopes)
    a_solved = container.solve(DepA, scopes=scopes)
    b_solved = container.solve(DepB, scopes=scopes)
    c_solved = container.solve(DepC, scopes=scopes)

    with container.enter_scope("app") as app_state:
        with container.enter_scope("request", state=app_state) as request_state:
            res = container.execute_sync(
                endpoint_solved, executor=SyncExecutor(), state=request_state
            )
            assert res == "ABC"
            # values should be cached as long as we're within the request scope
            holder[:] = "DEF"
            with container.enter_scope(
                "endpoint", state=request_state
            ) as endpoint_state:
                assert (
                    container.execute_sync(
                        endpoint_solved,
                        executor=SyncExecutor(),
                        state=endpoint_state,
                    )
                ) == "ABC"
            with container.enter_scope(
                "endpoint", state=request_state
            ) as endpoint_state:
                assert (
                    container.execute_sync(
                        c_solved, executor=SyncExecutor(), state=endpoint_state
                    )
                ) == "ABC"
            with container.enter_scope("endpoint"):
                assert (
                    container.execute_sync(
                        b_solved, executor=SyncExecutor(), state=endpoint_state
                    )
                ) == "AB"
            with container.enter_scope("endpoint"):
                assert (
                    container.execute_sync(
                        a_solved, executor=SyncExecutor(), state=endpoint_state
                    )
                ) == "A"
        # A is still cached because it is lifespan scoped
        assert (
            container.execute_sync(
                a_solved, executor=SyncExecutor(), state=endpoint_state
            )
        ) == "A"


def test_nested_lifecycle():

    state: typing.Dict[str, str] = dict.fromkeys(("A", "B", "C"), "uninitialized")

    def A() -> typing.Generator[None, None, None]:
        state["A"] = "initialized"
        yield
        state["A"] = "destroyed"

    def B(
        a: Annotated[None, Marker(A, scope="lifespan")]
    ) -> typing.Generator[None, None, None]:
        state["B"] = "initialized"
        yield
        state["B"] = "destroyed"

    def C(
        b: Annotated[None, Marker(B, scope="request")]
    ) -> typing.Generator[None, None, None]:
        state["C"] = "initialized"
        yield
        state["C"] = "destroyed"

    def endpoint(c: Annotated[None, Marker(C, scope="request")]) -> None:
        return

    container = Container()
    solved = container.solve(
        Dependant(endpoint, scope="endpoint"),
        scopes=["lifespan", "request", "endpoint"],
    )
    with container.enter_scope("lifespan") as app_state:
        with container.enter_scope("request", state=app_state) as request_state:
            assert list(state.values()) == ["uninitialized"] * 3
            with container.enter_scope(
                "endpoint", state=request_state
            ) as endpoint_state:
                container.execute_sync(
                    solved,
                    executor=SyncExecutor(),
                    state=endpoint_state,
                )
            assert list(state.values()) == ["initialized"] * 3
        assert list(state.values()) == ["initialized", "destroyed", "destroyed"]
    assert list(state.values()) == ["destroyed", "destroyed", "destroyed"]


@pytest.mark.anyio
async def test_enter_scope_concurrently():
    """We can enter the same scope from two different concurrent tasks"""

    container = Container()

    async def endpoint() -> None:
        async with container.enter_scope("request"):
            await anyio.sleep(
                0.05  # make sure execution overlaps, the number is arbitrary
            )

    async with anyio.create_task_group() as tg:
        tg.start_soon(endpoint)
        tg.start_soon(endpoint)
