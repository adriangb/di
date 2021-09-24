"""We should support callable classes as dependencies.
Modeled as call=cls.__call__, where the self argument is a dependency that depends on the class' constructor.
"""
import pytest

from di.container import Container
from di.dependency import Dependant
from di.params import Depends


def return_1() -> int:
    return 1


class Dependency:
    def __init__(self, value: int = Depends(return_1)) -> None:
        self.value = value

    def __call__(self: "Dependency", value: int = Depends(return_1)) -> "Dependency":
        self.call_value = self.value + value
        return self


@pytest.mark.anyio
async def test_callable_class():
    container = Container()
    res = await container.execute(Dependant(Dependency.__call__))
    assert res.call_value == 2


class ScopedDependency:
    def __init__(self, value: int = Depends(return_1)) -> None:
        self.value = value

    def __call__(
        self: "ScopedDependency" = Depends(scope="app"), value: int = Depends(return_1)
    ) -> "ScopedDependency":
        self.call_value = self.value + value
        return self


@pytest.mark.anyio
async def test_callable_class_instance_scoped():
    container = Container()
    async with container.enter_global_scope("app"):
        d1 = await container.execute(Dependant(ScopedDependency.__call__))
        assert d1.call_value == 2
        d1.value = 10
        d2 = await container.execute(Dependant(ScopedDependency.__call__))
        assert d2 is d1
        assert d2.call_value == 11
