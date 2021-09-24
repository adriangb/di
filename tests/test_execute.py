import pytest

from anydep.container import Container
from anydep.dependency import Dependant
from anydep.params import Depends


class vZero:
    def __call__(self) -> "vZero":
        return self


v0 = vZero()


class vOne:
    def __call__(self) -> "vOne":
        return self


v1 = vOne()


class vTwo:
    def __call__(self, one: vOne = Depends(v1)) -> "vTwo":
        self.one = one
        return self


v2 = vTwo()


class vThree:
    def __call__(self, zero: vZero = Depends(v0), one: vOne = Depends(v1)) -> "vThree":
        self.zero = zero
        self.one = one
        return self


v3 = vThree()


class vFour:
    def __call__(self, two: vTwo = Depends(v2)) -> "vFour":
        self.two = two
        return self


v4 = vFour()


class vFive:
    def __call__(
        self,
        zero: vZero = Depends(v0),
        three: vThree = Depends(v3),
        four: vFour = Depends(v4),
    ) -> "vFive":
        self.zero = zero
        self.three = three
        self.four = four
        return self


v5 = vFive()


@pytest.mark.anyio
async def test_execute():
    container = Container()
    res = await container.execute(Dependant(v5))
    assert res.three.zero is res.zero


@pytest.mark.anyio
async def test_bind():
    container = Container()
    async with container.enter_global_scope("something"):
        v3placeholder = object()
        v0placeholder = object()
        with container.bind(lambda **kwargs: v3placeholder, v3, scope="something"):
            with container.bind(lambda **kwargs: v0placeholder, v0, scope="something"):
                res = await container.execute(Dependant(v5))
                assert res.zero is v0placeholder
                assert res.three is v3placeholder
    res = await container.execute(Dependant(v5))
    assert res.zero is v0
    assert res.three is v3
    assert res.three.zero is res.zero


async def return_zero() -> int:
    return 0


async def bind(container: Container) -> None:
    container.bind(lambda: 10, return_zero, scope="something")


async def return_one(zero: int = Depends(return_zero)) -> int:
    return zero + 1


@pytest.mark.anyio
async def test_bind_within_execution():
    container = Container()
    async with container.enter_global_scope("something"):
        await container.execute(Dependant(bind))
        res = await container.execute(Dependant(return_one))
        assert res == 11
    res = await container.execute(Dependant(return_one))
    assert res == 1
