import pytest

from anydep.container import Container
from anydep.dependency import Dependant
from anydep.params import Depends


def return_one() -> int:
    return 1


def return_two(one: int = Depends(return_one), /) -> int:
    return one + 1


@pytest.mark.anyio
async def test_positional_only_parameters():
    container = Container()
    res = await container.execute(Dependant(return_two))
    assert res == 2
