import contextvars
import functools
import sys
import threading
import time
from contextlib import contextmanager
from typing import Any, AsyncGenerator, Generator, List

from di import ConcurrentAsyncExecutor, SyncExecutor

if sys.version_info < (3, 8):
    from typing_extensions import Literal
else:
    from typing import Literal

import anyio
import pytest

from di import AsyncExecutor, Container, Dependant
from di.exceptions import IncompatibleDependencyError, UnknownScopeError
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
    def __call__(self, one: Annotated[vOne, Dependant(v1)]) -> "vTwo":
        self.one = one
        return self


v2 = vTwo()


class vThree:
    def __call__(
        self, zero: Annotated[vZero, Dependant(v0)], one: Annotated[vOne, Dependant(v1)]
    ) -> "vThree":
        self.zero = zero
        self.one = one
        return self


v3 = vThree()


class vFour:
    def __call__(self, two: Annotated[vTwo, Dependant(v2)]) -> "vFour":
        self.two = two
        return self


v4 = vFour()


class vFive:
    def __call__(
        self,
        zero: Annotated[vZero, Dependant(v0)],
        three: Annotated[vThree, Dependant(v3)],
        four: Annotated[vFour, Dependant(v4)],
    ) -> "vFive":
        self.zero = zero
        self.three = three
        self.four = four
        return self


v5 = vFive()


def test_execute():
    container = Container()
    with container.enter_scope(None):
        res = container.execute_sync(
            container.solve(Dependant(v5)), executor=SyncExecutor()
        )
    assert res.three.zero is res.zero


def sync_callable_func() -> int:
    return 1


async def async_callable_func() -> int:
    return 1


def sync_gen_func() -> Generator[int, None, None]:
    yield 1


async def async_gen_func() -> AsyncGenerator[int, None]:
    yield 1


class SyncCallableCls:
    def __call__(self) -> int:
        return 1


class AsyncCallableCls:
    async def __call__(self) -> int:
        return 1


class Counter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counter = 0

    @property
    def counter(self) -> int:
        return self._counter

    @contextmanager
    def acquire(self) -> Generator[None, None, None]:
        with self._lock:
            self._counter += 1
        yield


def sync_callable_func_slow(counter: Counter) -> None:
    start = time.time()
    with counter.acquire():
        while counter.counter < 2:
            if time.time() - start > 0.5:
                raise TimeoutError(
                    "Tasks did not execute concurrently"
                )  # pragma: no cover
            time.sleep(0.005)
        return


async def async_callable_func_slow(counter: Counter) -> None:
    start = time.time()
    with counter.acquire():
        while counter.counter < 2:
            if time.time() - start > 0.5:
                raise TimeoutError(
                    "Tasks did not execute concurrently"
                )  # pragma: no cover
            await anyio.sleep(0.005)
        return


def sync_gen_func_slow(counter: Counter) -> Generator[None, None, None]:
    sync_callable_func_slow(counter)
    yield None


async def async_gen_func_slow(counter: Counter) -> AsyncGenerator[None, None]:
    await async_callable_func_slow(counter)
    yield None


class SyncCallableClsSlow:
    def __call__(self, counter: Counter) -> None:
        sync_callable_func_slow(counter)


class AsyncCallableClsSlow:
    async def __call__(self, counter: Counter) -> None:
        await async_callable_func_slow(counter)


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

    counter = Counter()
    container.register_by_type(Dependant(lambda: counter), Counter)

    async def collector(
        a: Annotated[None, Dependant(dep1, use_cache=False, sync_to_thread=sync1)],
        b: Annotated[None, Dependant(dep2, use_cache=False, sync_to_thread=sync2)],
    ):
        ...

    async with container.enter_scope(None):
        await container.execute_async(
            container.solve(Dependant(collector)), executor=ConcurrentAsyncExecutor()
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

    async def dep1(id: Annotated[int, Dependant(get_id)]) -> int:
        await anyio.sleep(delays[id])
        return id

    async def dep2(
        id: Annotated[int, Dependant(get_id)], one: Annotated[int, Dependant(dep1)]
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

    container = Container(scopes=("app", None))
    solved = container.solve(Dependant(dep2))

    async def execute_in_ctx(id: int) -> None:
        ctx.set(id)
        async with container.enter_scope(None):
            await container.execute_async(solved, executor=ConcurrentAsyncExecutor())

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

    async def collect1(obj: Annotated[object, Dependant(get_obj, scope=scope)]) -> None:
        objects.append(obj)

    async def collect2(obj: Annotated[object, Dependant(get_obj, scope=scope)]) -> None:
        objects.append(obj)

    container = Container(scopes=("app", None))
    solved1 = container.solve(Dependant(collect1))
    solved2 = container.solve(Dependant(collect2))

    async def execute_1():
        async with container.enter_scope(None):
            return await container.execute_async(
                solved1, executor=ConcurrentAsyncExecutor()
            )

    async def execute_2():
        async with container.enter_scope(None):
            return await container.execute_async(
                solved2, executor=ConcurrentAsyncExecutor()
            )

    async with container.enter_scope("app"):
        async with anyio.create_task_group() as tg:
            tg.start_soon(execute_1)
            await anyio.sleep(0.05)
            tg.start_soon(execute_2)

    assert (objects[0] is objects[1]) is use_cache


@pytest.mark.anyio
async def test_async_cm_de_in_sync_scope():
    """Cannot execute an async contextmanager-like dependency from within a sync scope"""

    async def dep() -> AsyncGenerator[None, None]:
        yield

    container = Container(scopes=("scope",))
    with container.enter_scope("scope"):
        with pytest.raises(
            IncompatibleDependencyError, match="canot be used in the sync scope"
        ):
            await container.execute_async(
                container.solve(Dependant(dep, scope="scope")), executor=AsyncExecutor()
            )


def test_unknown_scope():
    def bad_dep(v: Annotated[int, Dependant(lambda: 1, scope="request")]) -> int:
        return v

    container = Container(scopes=("app", "request"))
    solved = container.solve(Dependant(bad_dep))
    with container.enter_scope("app"):
        with pytest.raises(UnknownScopeError):
            container.execute_sync(solved, executor=SyncExecutor())
