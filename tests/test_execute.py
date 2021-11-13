import contextvars
import functools
import sys
import threading
import time
from contextlib import contextmanager
from typing import Any, AsyncGenerator, Generator, List

if sys.version_info < (3, 8):
    from typing_extensions import Literal
else:
    from typing import Literal

import anyio
import pytest

from di import Container, Dependant, Depends
from di.exceptions import IncompatibleDependencyError


class vZero:
    def __call__(self) -> "vZero":
        return self


v0 = vZero()


class vOne:
    def __call__(self) -> "vOne":
        return self


v1 = vOne()


class vTwo:
    def __call__(self, one: vOne = Depends(v1)) -> "vTwo":
        self.one = one
        return self


v2 = vTwo()


class vThree:
    def __call__(self, zero: vZero = Depends(v0), one: vOne = Depends(v1)) -> "vThree":
        self.zero = zero
        self.one = one
        return self


v3 = vThree()


class vFour:
    def __call__(self, two: vTwo = Depends(v2)) -> "vFour":
        self.two = two
        return self


v4 = vFour()


class vFive:
    def __call__(
        self,
        zero: vZero = Depends(v0),
        three: vThree = Depends(v3),
        four: vFour = Depends(v4),
    ) -> "vFive":
        self.zero = zero
        self.three = three
        self.four = four
        return self


v5 = vFive()


def test_execute():
    container = Container()
    res = container.execute_sync(container.solve(Dependant(v5)))
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


class SyncGenCls:
    def __call__(self) -> Generator[int, None, None]:
        yield 1


class AsyncGenCls:
    async def __call__(self) -> AsyncGenerator[int, None]:
        yield 1


@pytest.mark.parametrize(
    "dep",
    [
        sync_callable_func,
        async_callable_func,
        sync_gen_func,
        async_gen_func,
        SyncCallableCls(),
        AsyncCallableCls(),
        SyncGenCls(),
        AsyncGenCls(),
    ],
    ids=[
        "sync_callable_func",
        "async_callable_func",
        "sync_gen_func",
        "async_gen_func",
        "SyncCallableCls",
        "AsyncCallableCls",
        "SyncGenCls",
        "AsyncGenCls",
    ],
)
@pytest.mark.anyio
async def test_dependency_types(dep: Any):
    container = Container()
    assert (await container.execute_async(container.solve(Dependant(dep)))) == 1


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


class SyncGenClsSlow:
    def __call__(self, counter: Counter) -> Generator[None, None, None]:
        sync_callable_func_slow(counter)
        yield None


class AsyncGenClsSlow:
    async def __call__(self, counter: Counter) -> AsyncGenerator[None, None]:
        await async_callable_func_slow(counter)
        yield None


@pytest.mark.parametrize(
    "dep1",
    [
        sync_callable_func_slow,
        async_callable_func_slow,
        sync_gen_func_slow,
        async_gen_func_slow,
        SyncCallableClsSlow(),
        AsyncCallableClsSlow(),
        SyncGenClsSlow(),
        AsyncGenClsSlow(),
    ],
    ids=[
        "sync_callable_func",
        "async_callable_func",
        "sync_gen_func",
        "async_gen_func",
        "SyncCallableCls",
        "AsyncCallableCls",
        "SyncGenCls",
        "AsyncGenCls",
    ],
)
@pytest.mark.parametrize(
    "dep2",
    [
        sync_callable_func_slow,
        async_callable_func_slow,
        sync_gen_func_slow,
        async_gen_func_slow,
        SyncCallableClsSlow(),
        AsyncCallableClsSlow(),
        SyncGenClsSlow(),
        AsyncGenClsSlow(),
    ],
    ids=[
        "sync_callable_func",
        "async_callable_func",
        "sync_gen_func",
        "async_gen_func",
        "SyncCallableCls",
        "AsyncCallableCls",
        "SyncGenCls",
        "AsyncGenCls",
    ],
)
@pytest.mark.anyio
async def test_concurrency(dep1: Any, dep2: Any):
    container = Container()

    counter = Counter()
    container.bind(Dependant(lambda: counter), Counter)

    async def collector(
        a: None = Depends(dep1, share=False, sync_to_thread=True),
        b: None = Depends(dep2, share=False, sync_to_thread=True),
    ):
        ...

    await container.execute_async(container.solve(Dependant(collector)))


@pytest.mark.anyio
async def test_concurrent_executions_do_not_share_results():
    """If the same solved depedant is executed twice concurrently we should not
    overwrite the result of any sub-dependencies.
    """
    delays = {1: 0, 2: 0.01}
    ctx: contextvars.ContextVar[int] = contextvars.ContextVar("id")

    def get_id() -> int:
        return ctx.get()

    async def dep1(id: int = Depends(get_id)) -> int:
        await anyio.sleep(delays[id])
        return id

    async def dep2(id: int = Depends(get_id), one: int = Depends(dep1)) -> None:
        # let the other branch run
        await anyio.sleep(max(delays.values()))
        # check if the other branch replaced our value
        # ctx.get() serves as the source of truth
        expected = ctx.get()
        # and we check if the result was shared via caching or a bug in the
        # internal state of tasks (see https://github.com/adriangb/di/issues/18)
        assert id == expected  # replaced via caching
        assert one == expected  # replaced in results state

    container = Container()
    solved = container.solve(Dependant(dep2))

    async def execute_in_ctx(id: int) -> None:
        ctx.set(id)
        await container.execute_async(solved)

    async with anyio.create_task_group() as tg:
        async with container.enter_global_scope("app"):
            tg.start_soon(functools.partial(execute_in_ctx, 1))
            tg.start_soon(functools.partial(execute_in_ctx, 2))


@pytest.mark.anyio
@pytest.mark.parametrize("scope,shared", [(None, False), ("global", True)])
async def test_concurrent_executions_share_cache(
    scope: Literal[None, "global"], shared: bool
):
    """Check that global / local scopes are respected during concurrent execution"""
    objects: List[object] = []

    def get_obj() -> object:
        return object()

    async def collect1(obj: object = Depends(get_obj, scope=scope)) -> None:
        objects.append(obj)

    async def collect2(obj: object = Depends(get_obj, scope=scope)) -> None:
        objects.append(obj)

    container = Container()
    solved1 = container.solve(Dependant(collect1))
    solved2 = container.solve(Dependant(collect2))

    async with container.enter_global_scope("global"):
        async with anyio.create_task_group() as tg:
            tg.start_soon(functools.partial(container.execute_async, solved1))
            await anyio.sleep(0.05)
            tg.start_soon(functools.partial(container.execute_async, solved2))

    assert (objects[0] is objects[1]) is shared


@pytest.mark.anyio
async def test_async_cm_de_in_sync_scope():
    """Cannot execute an async contextmanager-like dependency from within a sync scope"""

    async def dep() -> AsyncGenerator[None, None]:
        yield

    container = Container()
    with container.enter_local_scope("test"):
        with pytest.raises(
            IncompatibleDependencyError, match="canot be used in the sync scope"
        ):
            await container.execute_async(container.solve(Dependant(dep, scope="test")))
