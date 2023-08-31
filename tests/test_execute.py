import contextvars
import functools
import sys
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Generator, List

if sys.version_info < (3, 8):
    from typing_extensions import Literal
else:
    from typing import Literal

import anyio
import pytest

from di import Container, ScopeState, bind_by_type
from di.concurrency import as_async
from di.dependent import Dependent, Marker
from di.exceptions import IncompatibleDependencyError, UnknownScopeError
from di.executors import AsyncExecutor, ConcurrentAsyncExecutor, SyncExecutor
from di.typing import Annotated


class vZero:
    def __call__(self) -> "vZero":
        return self


v0 = vZero()


class vOne:
    def __call__(self) -> "vOne":
        return self


v1 = vOne()


class vTwo:
    def __call__(self, one: Annotated[vOne, Marker(v1)]) -> "vTwo":
        self.one = one
        return self


v2 = vTwo()


class vThree:
    def __call__(
        self, zero: Annotated[vZero, Marker(v0)], one: Annotated[vOne, Marker(v1)]
    ) -> "vThree":
        self.zero = zero
        self.one = one
        return self


v3 = vThree()


class vFour:
    def __call__(self, two: Annotated[vTwo, Marker(v2)]) -> "vFour":
        self.two = two
        return self


v4 = vFour()


class vFive:
    def __call__(
        self,
        zero: Annotated[vZero, Marker(v0)],
        three: Annotated[vThree, Marker(v3)],
        four: Annotated[vFour, Marker(v4)],
    ) -> "vFive":
        self.zero = zero
        self.three = three
        self.four = four
        return self


v5 = vFive()


def test_execute():
    container = Container()
    with container.enter_scope(None) as state:
        res = container.solve(Dependent(v5), scopes=[None]).execute_sync(
            executor=SyncExecutor(),
            state=state,
        )
    assert res.three.zero is res.zero


@dataclass
class Synchronizer:
    started: List[anyio.Event]
    shutdown: anyio.Event


def _sync_callable_func_slow(synchronizer: Synchronizer) -> None:
    # anyio requires arguments to from_thread.run to be coroutines
    async def set() -> None:
        synchronizer.started.pop().set()

    # trio requires set() to be called from within an async task
    anyio.from_thread.run(set)
    anyio.from_thread.run(synchronizer.shutdown.wait)


sync_callable_func_slow = as_async(_sync_callable_func_slow)


async def async_callable_func_slow(synchronizer: Synchronizer) -> None:
    synchronizer.started.pop().set()
    await synchronizer.shutdown.wait()


@as_async
def sync_gen_func_slow(synchronizer: Synchronizer) -> Generator[None, None, None]:
    _sync_callable_func_slow(synchronizer)
    yield None


async def async_gen_func_slow(synchronizer: Synchronizer) -> AsyncGenerator[None, None]:
    await async_callable_func_slow(synchronizer)
    yield None


class SyncCallableClsSlow:
    @as_async
    def __call__(self, synchronizer: Synchronizer) -> None:
        _sync_callable_func_slow(synchronizer)


class AsyncCallableClsSlow:
    async def __call__(self, synchronizer: Synchronizer) -> None:
        await async_callable_func_slow(synchronizer)


@pytest.mark.parametrize(
    "dep1,sync1",
    [
        (sync_callable_func_slow, True),
        (async_callable_func_slow, False),
        (sync_gen_func_slow, True),
        (async_gen_func_slow, False),
        (SyncCallableClsSlow(), True),
        (AsyncCallableClsSlow(), False),
    ],
    ids=[
        "sync_callable_func",
        "async_callable_func",
        "sync_gen_func",
        "async_gen_func",
        "SyncCallableCls",
        "AsyncCallableCls",
    ],
)
@pytest.mark.parametrize(
    "dep2,sync2",
    [
        (sync_callable_func_slow, True),
        (async_callable_func_slow, False),
        (sync_gen_func_slow, True),
        (async_gen_func_slow, False),
        (SyncCallableClsSlow(), True),
        (AsyncCallableClsSlow(), False),
    ],
    ids=[
        "sync_callable_func",
        "async_callable_func",
        "sync_gen_func",
        "async_gen_func",
        "SyncCallableCls",
        "AsyncCallableCls",
    ],
)
@pytest.mark.anyio
async def test_concurrency_async(dep1: Any, sync1: bool, dep2: Any, sync2: bool):
    container = Container()

    synchronizer = Synchronizer([anyio.Event(), anyio.Event()], anyio.Event())
    container.bind(bind_by_type(Dependent(lambda: synchronizer), Synchronizer))

    async def collector(
        a: Annotated[None, Marker(dep1, use_cache=False)],
        b: Annotated[None, Marker(dep2, use_cache=False)],
    ):
        ...

    async def monitor() -> None:
        with anyio.fail_after(1):
            async with anyio.create_task_group() as tg:
                for e in synchronizer.started:
                    tg.start_soon(e.wait)
        synchronizer.shutdown.set()

    async with anyio.create_task_group() as tg:
        async with container.enter_scope(None) as state:
            tg.start_soon(monitor)
            await container.solve(Dependent(collector), scopes=[None]).execute_async(
                executor=ConcurrentAsyncExecutor(),
                state=state,
            )


@pytest.mark.anyio
async def test_concurrent_executions_do_not_use_cache_results():
    """If the same solved depedant is executed twice concurrently we should not
    overwrite the result of any sub-dependencies.
    """
    delays = {1: 0, 2: 0.01}
    ctx: contextvars.ContextVar[int] = contextvars.ContextVar("id")

    def get_id() -> int:
        return ctx.get()

    async def dep1(id: Annotated[int, Marker(get_id)]) -> int:
        await anyio.sleep(delays[id])
        return id

    async def dep2(
        id: Annotated[int, Marker(get_id)], one: Annotated[int, Marker(dep1)]
    ) -> None:
        # let the other branch run
        await anyio.sleep(max(delays.values()))
        # check if the other branch replaced our value
        # ctx.get() serves as the source of truth
        expected = ctx.get()
        # and we check if the result was use_cached via caching or a bug in the
        # internal state of tasks (see https://github.com/adriangb/di/issues/18)
        assert id == expected  # replaced via caching
        assert one == expected  # replaced in results state

    container = Container()
    solved = container.solve(Dependent(dep2), scopes=[None])

    async def execute_in_ctx(id: int) -> None:
        ctx.set(id)
        async with container.enter_scope(None) as state:
            await solved.execute_async(executor=ConcurrentAsyncExecutor(), state=state)

    async with anyio.create_task_group() as tg:
        async with container.enter_scope("app"):
            tg.start_soon(functools.partial(execute_in_ctx, 1))
            tg.start_soon(functools.partial(execute_in_ctx, 2))


@pytest.mark.anyio
@pytest.mark.parametrize("scope,use_cache", [(None, False), ("app", True)])
async def test_concurrent_executions_use_cache(
    scope: Literal[None, "app"], use_cache: bool
):
    """Check that global / local scopes are respected during concurrent execution"""
    objects: List[object] = []

    def get_obj() -> object:
        return object()

    async def collect1(
        obj: Annotated[object, Marker(get_obj, scope=scope, use_cache=use_cache)]
    ) -> None:
        objects.append(obj)
        await anyio.sleep(0.01)

    async def collect2(
        obj: Annotated[object, Marker(get_obj, scope=scope, use_cache=use_cache)]
    ) -> None:
        objects.append(obj)

    container = Container()
    solved1 = container.solve(Dependent(collect1), scopes=["app", None])
    solved2 = container.solve(Dependent(collect2), scopes=["app", None])

    async def execute_1(state: ScopeState):
        async with container.enter_scope(None, state=state) as state:
            return await solved1.execute_async(
                executor=ConcurrentAsyncExecutor(), state=state
            )

    async def execute_2(state: ScopeState):
        async with container.enter_scope(None, state=state) as state:
            return await solved2.execute_async(
                executor=ConcurrentAsyncExecutor(), state=state
            )

    async with container.enter_scope("app") as state:
        async with anyio.create_task_group() as tg:
            tg.start_soon(execute_1, state)
            await anyio.sleep(0.005)
            tg.start_soon(execute_2, state)

    assert (objects[0] is objects[1]) is (use_cache and scope == "app")


@pytest.mark.anyio
async def test_async_cm_de_in_sync_scope():
    """Cannot execute an async contextmanager-like dependency from within a sync scope"""

    async def dep() -> AsyncGenerator[None, None]:
        yield

    container = Container()
    with container.enter_scope(None) as state:
        with pytest.raises(
            IncompatibleDependencyError, match="cannot be used in the sync scope"
        ):
            await container.solve(
                Dependent(dep, scope=None), scopes=[None]
            ).execute_async(
                executor=AsyncExecutor(),
                state=state,
            )


def test_unknown_scope() -> None:
    def bad_dep(v: Annotated[int, Marker(lambda: 1, scope="foo")]) -> int:
        return v

    container = Container()
    with pytest.raises(UnknownScopeError):
        container.solve(Dependent(bad_dep, scope="app"), scopes=["app"])
