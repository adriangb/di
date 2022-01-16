from typing import Tuple

import pytest

from di import CallableClassDependant, Container, SyncExecutor


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

    container = Container(scopes=("app", "request"))

    dep = CallableClassDependant(CallableClass, scope="request", instance_scope="app")
    solved = container.solve(dep)

    with container.enter_scope("app"):
        with container.enter_scope("request"):
            instance1_1, v1_1 = container.execute_sync(solved, executor=SyncExecutor())
        with container.enter_scope("request"):
            instance1_2, v1_2 = container.execute_sync(solved, executor=SyncExecutor())
        assert instance1_1 is instance1_2
        assert v1_1 == 1
        assert v1_2 == 2

    with container.enter_scope("app"):
        with container.enter_scope("request"):
            instance2_1, v2_1 = container.execute_sync(solved, executor=SyncExecutor())
        with container.enter_scope("request"):
            instance2_2, v2_2 = container.execute_sync(solved, executor=SyncExecutor())
        assert instance2_1 is instance2_2
        assert v2_1 == 1
        assert v2_2 == 2

    assert instance2_1 is not instance1_1


def test_not_a_class():
    with pytest.raises(TypeError):
        CallableClassDependant(lambda: None)  # type: ignore[arg-type]
