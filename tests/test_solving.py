from collections import defaultdict
from typing import AsyncGenerator, DefaultDict, Generator, Union

import pytest

from anydep.container import Container
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
    def __init__(self) -> None:
        self.value = 5
        counter["Class"] += 1


def collector(
    v1: int = Depends(async_call),
    v2: int = Depends(async_gen),
    v3: int = Depends(sync_call),
    v4: int = Depends(sync_gen),
    v5: Class = Depends(Class),
) -> int:
    counter["collector"] += 1
    return v1 + v2 + v3 + v4 + v5.value


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
    async with container.enter_scope("app"):
        assert all(v is None for v in lifetimes.values())
        for _ in range(2):  # to check that values are cached
            r = await container.execute(parent)
            assert all(v == "started" for v in lifetimes.values())
    assert all(v == "finished" for v in lifetimes.values())
    assert r == 30
    assert counter == {"async_call": 1, "async_gen": 1, "sync_call": 1, "sync_gen": 1, "Class": 1, "collector": 1}
