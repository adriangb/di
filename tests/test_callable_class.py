import pytest

from anydep.container import Container
from anydep.params import CallableClass


class MyClass:
    def __init__(self) -> None:
        self.value = 2

    async def __call__(self):
        return self.value ** 2


class MyChildClass(MyClass):
    def __init__(self) -> None:
        self.value = 3


@pytest.mark.anyio
async def test_callable_class():
    container = Container()
    async with container.enter_global_scope("app"):
        assert 4 == await container.execute(CallableClass(MyClass))
        assert 9 == await container.execute(CallableClass(MyChildClass))
