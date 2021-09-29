import threading
import time
from contextlib import contextmanager
from typing import Any, AsyncGenerator, Generator

import anyio
import pytest

from di.container import Container
from di.dependency import Dependant
from di.params import Depends


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
            if time.time() - start > 10:
                raise TimeoutError(
                    "Tasks did not execute concurrently"
                )  # pragma: no cover
            time.sleep(0.005)
        return


async def async_callable_func_slow(counter: Counter) -> None:
    start = time.time()
    with counter.acquire():
        while counter.counter < 2:
            if time.time() - start > 10:
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
        a: None = Depends(dep1, shared=False), b: None = Depends(dep2, shared=False)
    ):
        ...

    await container.execute_async(container.solve(Dependant(collector)))
