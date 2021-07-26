from anydep.models import Dependant
from typing import AsyncGenerator, Dict, Generator, Union

import pytest

from anydep.cache import CachePolicy
from anydep.container import Container
from anydep.lifespan import AsyncExitStackLifespan
from anydep.params import Depends
from tests.cache_policies import CacheByCall, CacheByDepId, NoCache

counter = {
    "async_call": 0,
    "async_gen": 0,
    "sync_call": 0,
    "sync_gen": 0,
    "Class": 0,
    "sub_dep": 0,
}

lifetimes: Dict[str, Union[None, str]] = {"async_gen": None, "sync_gen": None}


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
    counter["sub_dep"] += 1
    return v1 + v2 + v3 + v4 + v5.value


def parent(v1: int = Depends(collector), v2: int = Depends(collector)) -> int:
    return v1 + v2


@pytest.mark.anyio
@pytest.mark.parametrize(
    "cache_policy, expected",
    [
        (CacheByCall(), {"async_call": 1, "async_gen": 1, "sync_call": 1, "sync_gen": 1, "Class": 1, "sub_dep": 1}),
        (CacheByDepId(), {"async_call": 1, "async_gen": 1, "sync_call": 1, "sync_gen": 1, "Class": 1, "sub_dep": 2}),
        (NoCache(), {"async_call": 2, "async_gen": 2, "sync_call": 2, "sync_gen": 2, "Class": 2, "sub_dep": 2}),
    ],
    ids=["cache-by-dependant-call", "cache-by-depedant-id", "no-cache"],
)
async def test_solve_call_id_cache(cache_policy: CachePolicy, expected: Dict[str, int]):
    for k in counter.keys():
        counter[k] = 0
    for k in lifetimes.keys():
        lifetimes[k] = None

    dep = Dependant(call=parent)
    container = Container()
    task = container.compile_task(dep, cache_policy=cache_policy)
    async with AsyncExitStackLifespan() as lifespan:
        assert all(v is None for v in lifetimes.values())
        r = await container.execute(task=task, lifespan=lifespan)
        assert all(v == "started" for v in lifetimes.values())
    assert all(v == "finished" for v in lifetimes.values())
    assert r == 30
    assert counter == expected
