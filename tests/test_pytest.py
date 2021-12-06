from typing import AsyncGenerator, List

import pytest

from di.pytest import Depends, inject


class Log(List[str]):
    pass


def dep(log: Log = Depends(Log)) -> int:
    log.append("dep")
    return 1


async def generator_dep(
    inner_val: int = Depends(dep), log: Log = Depends(Log)
) -> AsyncGenerator[int, None]:
    log.append("generator_dep setup")
    yield inner_val + 1
    log.append("generator_dep teardown")


@pytest.mark.anyio
@inject
async def test_inject(v: int = Depends(generator_dep), log: Log = Depends(Log)) -> None:
    assert v == 2
    assert log == ["dep", "generator_dep setup"]  # teardown hasn't run yet
