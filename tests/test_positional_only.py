import pytest

from di.container import Container
from di.dependency import Dependant
from di.params import Depends


def return_one() -> int:
    return 1


def return_two(one: int = Depends(return_one), /) -> int:
    return one + 1


@pytest.mark.anyio
async def test_positional_only_parameters():
    container = Container()
    res = container.execute_sync(container.solve(Dependant(return_two)))
    assert res == 2
