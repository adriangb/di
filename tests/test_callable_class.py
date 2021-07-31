import pytest

from anydep.container import Container
from anydep.params import CallableClass


class Config:
    def __init__(self) -> None:
        self.value: int = 1


class MyClass:
    def __init__(self, value: int = 2) -> None:
        self.value = value

    async def __call__(self):
        return self.value


class MyChildClass(MyClass):
    def __init__(self, value: int = 2) -> None:
        self.value = value ** 2


def myclass_from_config(config: Config) -> MyClass:
    return MyClass(value=config.value)


@pytest.mark.anyio
async def test_loading_from_config():
    container = Container()
    async with container.enter_global_scope("app"):
        container.bind(MyClass, myclass_from_config)
        assert 1 == await container.execute(CallableClass(MyClass))


@pytest.mark.anyio
async def test_inheritence():
    container = Container()
    async with container.enter_global_scope("app"):
        assert 2 == await container.execute(CallableClass(MyClass))
        assert 4 == await container.execute(CallableClass(MyChildClass))
