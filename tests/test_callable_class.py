import pytest

from di import Container
from di.dependant import CallableClassDependant
from di.types.providers import DependencyProviderType


def test_callable_class_dependant():
    """CallableClassDependant accepts a callable class and returns the value
    of that class' __call__.
    The instance can be cached in a different scope than the result of __call__.
    In this test, the instance is persisted in the "app" scope while __call__ is re-computed
    every time.
    """

    class CallableClass:
        def __init__(self) -> None:
            self.counter = 0

        def __call__(self) -> int:
            self.counter += 1
            return id(self) + self.counter

    container = Container()

    dep1 = CallableClassDependant(CallableClass, instance_scope="app")
    solved1 = container.solve(dep1)
    with container.enter_global_scope("app"):
        v1 = container.execute_sync(solved1)
        v2 = container.execute_sync(solved1)

    dep2 = CallableClassDependant(CallableClass, instance_scope="app")
    solved2 = container.solve(dep2)
    with container.enter_global_scope("app"):
        v3 = container.execute_sync(solved2)
        v4 = container.execute_sync(solved2)

    assert v1 == v2 - 1 and v1 != v3 and v3 == v4 - 1


class InitFailsCls:
    def __init__(self, x: int = 1) -> None:
        assert x == 2
        self.x = x

    def __call__(self) -> None:
        assert self.x == 2


async def pointless_async_provider() -> InitFailsCls:
    return InitFailsCls(2)


@pytest.mark.parametrize(
    "cls_provider", [lambda: InitFailsCls(2), pointless_async_provider]
)
@pytest.mark.anyio
async def test_cls_provider(cls_provider: DependencyProviderType[InitFailsCls]):
    """An alternative constructor can be provided to allow composition instead of having to
    inherit and override the class constructor.
    """
    container = Container()
    dep = CallableClassDependant(InitFailsCls, cls_provider=cls_provider)  # type: ignore  # mypy has trouble with this, Pyalnce works fine
    solved = container.solve(dep)

    await container.execute_async(solved)


def test_not_a_class():
    with pytest.raises(TypeError):
        CallableClassDependant(lambda: None)
