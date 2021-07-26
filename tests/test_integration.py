from __future__ import annotations

from typing import AsyncGenerator, Generator

import pytest

from anydep.container import Container
from anydep.lifespan import AsyncExitStackDependencyLifespan
from anydep.params import Depends


async def async_call() -> int:
    return 1


async def async_gen() -> AsyncGenerator[int, None]:
    yield 1


def sync_call() -> int:
    return 1


def sync_gen() -> Generator[int, None, None]:
    yield 1


counter_holder = {"counter": 0}


class Class:
    def __init__(self) -> None:
        self.value = 1
        counter_holder["counter"] += 1


def sub_dep(
    v0: Class,
    v1: int = Depends(async_call),
    v2: int = Depends(async_gen),
    v4: int = Depends(sync_call),
    v5: int = Depends(sync_gen),
) -> int:
    return v0.value + v1 + v2 + v4 + v5


def requestor(
    v0: Class,
    v1: int = Depends(async_call),
    v2: int = Depends(async_gen),
    v4: int = Depends(sync_call),
    v5: int = Depends(sync_gen),
    v7: Class = Depends(Class),
    v8: int = Depends(sub_dep),
    v9: Class = Depends(),
    v10: int = 2,
):
    assert v10 == 2
    return v0.value + v1 + v2 + v4 + v5 + v7.value + v8 + v9.value + v10


@pytest.mark.anyio
async def test_all():
    counter_holder["counter"] = 0
    dep = Depends(call=requestor)
    container = Container()
    container.wire_dependant(dep, cache={})
    async with AsyncExitStackDependencyLifespan() as lifespan:
        r = await container.solve(dep, lifespan=lifespan, solved={Depends(Class): Class()})
    assert counter_holder["counter"] == 1  # basic check for caching
    assert r == 14  # empirical for now
