import pytest

from di import Container
from di.dependant import CallableClassDependant


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

    dep1 = CallableClassDependant(CallableClass, instance_scope="app", scope=None)
    solved1 = container.solve(dep1)
    with container.enter_global_scope("app"):
        v1 = container.execute_sync(solved1)
        v2 = container.execute_sync(solved1)

    dep2 = CallableClassDependant(CallableClass, instance_scope="app", scope=None)
    solved2 = container.solve(dep2)
    with container.enter_global_scope("app"):
        v3 = container.execute_sync(solved2)
        v4 = container.execute_sync(solved2)

    assert v1 == v2 - 1 and v1 != v3 and v3 == v4 - 1


def test_not_a_class():
    with pytest.raises(TypeError):
        CallableClassDependant(lambda: None)
