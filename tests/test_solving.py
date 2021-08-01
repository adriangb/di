from collections import defaultdict
from typing import AsyncGenerator, DefaultDict, Generator, Union

import pytest

from anydep.container import Container
from anydep.exceptions import CircularDependencyError, WiringError
from anydep.models import Dependant
from anydep.params import Depends

counter: DefaultDict[str, int] = defaultdict(int)

lifetimes: DefaultDict[str, Union[None, str]] = defaultdict(lambda: None)


async def async_call() -> int:
    counter["async_call"] += 1
    return 1


async def async_gen() -> AsyncGenerator[int, None]:
    counter["async_gen"] += 1
    lifetimes["async_gen"] = "started"
    yield 2
    lifetimes["async_gen"] = "finished"


def sync_call() -> int:
    counter["sync_call"] += 1
    return 3


def sync_gen() -> Generator[int, None, None]:
    counter["sync_gen"] += 1
    lifetimes["sync_gen"] = "started"
    yield 4
    lifetimes["sync_gen"] = "finished"


class Class:
    def __init__(self, value: int = 5) -> None:
        self.value = value
        counter["Class"] += 1


class CallableClass:
    def __call__(self) -> int:
        return 6


callable_class = CallableClass()


class AsyncCallableClass:
    async def __call__(self) -> int:
        return 7


async_callable_class = AsyncCallableClass()


def collector(
    v0: Class,
    v1: int = Depends(async_call),
    v2: int = Depends(async_gen),
    v3: int = Depends(sync_call),
    v4: int = Depends(sync_gen),
    v5: Class = Depends(Class),
    v5b: Class = Depends(),
    v6: int = Depends(callable_class),
    v7: int = Depends(async_callable_class),
) -> int:
    counter["collector"] += 1
    return v0.value + v1 + v2 + v3 + v4 + v5.value + v5b.value + v6 + v7


def parent(v1: int = Depends(collector), v2: int = Depends(collector)) -> int:
    return v1 + v2


@pytest.fixture
def reset():
    for k in counter.copy().keys():
        counter.pop(k)
    for k in lifetimes.copy().keys():
        lifetimes.pop(k)


@pytest.mark.anyio
async def test_solve_call_id_cache(reset: None) -> None:
    container = Container()
    for iteration in range(1, 3):
        async with container.enter_global_scope("app"):
            for _ in range(2):  # to check that values are cached
                dependant = Dependant(parent)
                value = await container.execute(dependant)
                assert all(v == "started" for v in lifetimes.values())
        assert all(v == "finished" for v in lifetimes.values())
        assert value == 76
        assert counter == {
            "async_call": iteration,
            "async_gen": iteration,
            "sync_call": iteration,
            "sync_gen": iteration,
            "Class": iteration,
            "collector": iteration,
        }


@pytest.mark.anyio
async def test_no_default_no_depends():
    def method(value):
        ...

    container = Container()
    async with container.enter_global_scope("app"):
        with pytest.raises(WiringError):
            await container.execute(Dependant(method))


@pytest.mark.anyio
async def test_solve_default():
    def method(value: int = 5) -> int:
        return value

    container = Container()
    async with container.enter_global_scope("app"):
        assert 5 == await container.execute(Dependant(method))


class C1:
    def __init__(self, c2: "C2") -> None:
        ...


class C2:
    def __init__(self, c1: C1) -> None:
        ...


@pytest.mark.anyio
async def test_cycles():
    container = Container()
    async with container.enter_global_scope("app"):
        with pytest.raises(CircularDependencyError):
            await container.execute(Dependant(C1))
