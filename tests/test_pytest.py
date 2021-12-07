from typing import AsyncGenerator, List

import pytest

from di import Depends
from di.pytest import inject


class Log(List[str]):
    pass


def dep(log: Log) -> int:
    log.append("dep")
    return 1


async def generator_dep(
    log: Log, inner_val: int = Depends(dep, scope="function")
) -> AsyncGenerator[int, None]:
    log.append("generator_dep setup")
    yield inner_val + 1
    log.append("generator_dep teardown")


@pytest.mark.anyio
@inject
async def test_inject(
    log: Log, v: int = Depends(generator_dep, scope="function")
) -> None:
    assert v == 2
    assert log == ["dep", "generator_dep setup"]  # teardown hasn't run yet
