from typing import Tuple

import pytest

from di import Container
from di.dependant import CallableClassDependant


class CallableClass:
    def __init__(self) -> None:
        self.counter = 0

    def __call__(self) -> Tuple["CallableClass", int]:
        self.counter += 1
        return (self, self.counter)


def test_callable_class_dependant():
    """CallableClassDependant accepts a callable class and returns the value
    of that class' __call__.
    The instance can be cached in a different scope than the result of __call__.
    In this test, the instance is persisted in the "app" scope while __call__ is re-computed
    every time.
    """

    container = Container()

    dep1 = CallableClassDependant(CallableClass, instance_scope="app")
    solved1 = container.solve(dep1)
    with container.enter_scope("app"):
        instance1_1, v1_1 = container.execute_sync(solved1)
        instance1_2, v1_2 = container.execute_sync(solved1)
        assert instance1_1 is instance1_2
        assert v1_1 == 1
        assert v1_2 == 2

    dep2 = CallableClassDependant(CallableClass, instance_scope="app")
    solved2 = container.solve(dep2)
    with container.enter_scope("app"):
        instance2_1, v2_1 = container.execute_sync(solved2)
        instance2_2, v2_2 = container.execute_sync(solved2)
        assert instance2_1 is instance2_2
        assert v2_1 == 1
        assert v2_2 == 2

    assert instance2_1 is not instance1_1


class InitFailsCls:
    def __init__(self, x: int = 1) -> None:
        assert x == 2
        self.x = x

    def __call__(self) -> None:
        assert self.x == 2


def test_not_a_class():
    with pytest.raises(TypeError):
        CallableClassDependant(lambda: None)
