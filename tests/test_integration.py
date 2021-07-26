from __future__ import annotations

import asyncio
from typing import AsyncGenerator, Generator

from anydep.container import Container
from anydep.lifespan import AsyncExitStackDependencyLifespan
from anydep.models import Dependant
from anydep.params import Depends


async def async_call() -> int:
    return 1


async def async_gen() -> AsyncGenerator[int, None]:
    yield 1


def sync_call() -> int:
    return 1


def sync_gen() -> Generator[int, None, None]:
    yield 1


class Class:
    calls: int = 0

    def __init__(self) -> None:
        self.value = 1
        Class.calls += 1


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


async def amain(dep: Dependant, container: Container):
    async with AsyncExitStackDependencyLifespan() as lifespan:
        return await container.solve(dep, lifespan=lifespan, solved={Depends(Class): Class()})


def test_all():
    dep = Depends(call=requestor)
    c = Container()
    c.wire_dependant(dep, cache={})
    r = asyncio.run(amain(dep, c))
    assert Class.calls == 1  # basic check for caching
    assert r == 14  # empirical for now
    print(r)
