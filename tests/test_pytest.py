import pytest

from di.pytest import Depends, inject


async def dep() -> int:
    return 1


@pytest.mark.anyio
@inject
async def test_inject(v: int = Depends(dep)) -> None:
    assert v == 1
