from typing import Any, AsyncGenerator, Generator

import pytest

from di.container import Container
from di.dependency import Dependant
from di.params import Depends


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


def sync_callable_func() -> int:
    return 1


async def async_callable_func() -> int:
    return 1


def sync_gen_func() -> Generator[int, None, None]:
    yield 1


async def async_gen_func() -> AsyncGenerator[int, None]:
    yield 1


class SyncCallableCls:
    def __call__(self) -> int:
        return 1


class AsyncCallableCls:
    async def __call__(self) -> int:
        return 1


class SyncGenCls:
    def __call__(self) -> Generator[int, None, None]:
        yield 1


class AsyncGenCls:
    async def __call__(self) -> AsyncGenerator[int, None]:
        yield 1


@pytest.mark.parametrize(
    "dep",
    [
        sync_callable_func,
        async_callable_func,
        sync_gen_func,
        async_gen_func,
        SyncCallableCls(),
        AsyncCallableCls(),
        SyncGenCls(),
        AsyncGenCls(),
    ],
)
@pytest.mark.anyio
async def test_dependency_types(dep: Any):
    container = Container()
    assert (await container.execute(Dependant(dep))) == 1
