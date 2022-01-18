import inspect
import sys
from typing import Tuple, Type, TypeVar

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

import pytest

from di import Container, Dependant, SyncExecutor
from di.api.providers import DependencyProviderType
from di.api.scopes import Scope

T = TypeVar("T")


class CallableClassProtocol(Protocol[T]):
    """A callable class that has a __call__ that is valid as dependency provider"""

    __call__: DependencyProviderType[T]


def CallableClassDependant(
    call: Type[CallableClassProtocol[T]],
    *,
    instance_scope: Scope = None,
    scope: Scope = None,
    share: bool = True,
    wire: bool = True,
) -> Dependant[T]:
    """Create a Dependant that will create and call a callable class

    The class instance can come from the class' constructor (by default)
    or be provided by cls_provider.
    """
    if not (inspect.isclass(call) and hasattr(call, "__call__")):
        raise TypeError("call must be a callable class")
    instance = Dependant[CallableClassProtocol[T]](
        call,
        scope=instance_scope,
        share=True,
        wire=wire,
    )
    return Dependant[T](
        call=call.__call__,
        scope=scope,
        share=share,
        wire=wire,
        overrides={"self": instance},
    )


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
