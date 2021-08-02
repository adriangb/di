from collections import defaultdict
from typing import Any, AsyncGenerator, DefaultDict, Generator, Union

import pytest

counter: DefaultDict[Any, int] = defaultdict(int)

lifetimes: DefaultDict[Any, Union[None, str]] = defaultdict(lambda: None)


@pytest.fixture(autouse=True, scope="function")
def reset_dependencies():
    for k in counter.copy().keys():
        counter.pop(k)
    for k in lifetimes.copy().keys():
        lifetimes.pop(k)


async def async_call() -> int:
    counter[async_call] += 1
    return 1


async def async_gen() -> AsyncGenerator[int, None]:
    counter[async_gen] += 1
    lifetimes[async_gen] = "started"
    yield 2
    lifetimes[async_gen] = "finished"


def sync_call() -> int:
    counter[sync_call] += 1
    return 3


def sync_gen() -> Generator[int, None, None]:
    counter[sync_gen] += 1
    lifetimes[sync_gen] = "started"
    yield 4
    lifetimes[sync_gen] = "finished"


class Class:
    def __init__(self, value: int = 5) -> None:
        self.value = value
        counter[Class] += 1


class CallableClass:
    def __call__(self) -> int:
        counter[self] += 1
        return 6


callable_class = CallableClass()


class AsyncCallableClass:
    async def __call__(self) -> int:
        counter[self] += 1
        return 7


async_callable_class = AsyncCallableClass()


class AsyncCMClass:
    async def __aenter__(self) -> int:
        counter[AsyncCMClass] += 1
        lifetimes[AsyncCMClass] = "started"
        return 9

    async def __aexit__(self, *args, **kwargs) -> None:
        lifetimes[AsyncCMClass] = "finished"


class SyncCMClass:
    def __enter__(self) -> int:
        counter[SyncCMClass] += 1
        lifetimes[SyncCMClass] = "started"
        return 9

    def __exit__(self, *args, **kwargs) -> None:
        lifetimes[SyncCMClass] = "finished"
