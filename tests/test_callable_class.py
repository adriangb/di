"""We should support callable classes as dependencies.
Modeled as call=cls.__call__, where the self argument is a dependency that depends on the class' constructor.
"""
from di.container import Container
from di.dependency import Dependant
from di.params import Depends


def return_1() -> int:
    return 1


def return_2() -> int:
    return 2


class Dependency:
    def __init__(self, value: int = Depends(return_1)) -> None:
        self.value = value

    def __call__(self: "Dependency", value: int = Depends(return_2)) -> "Dependency":
        self.call_value = self.value + value
        return self


def test_callable_class():
    container = Container()
    solved = container.solve(Dependant(Dependency.__call__))
    res = container.execute_sync(solved)
    assert res.call_value == 3


class ScopedDependency:
    def __init__(self, value: int = Depends(return_1, scope="app")) -> None:
        self.value = value

    def __call__(
        self: "ScopedDependency" = Depends(scope="app"), value: int = Depends(return_2)
    ) -> "ScopedDependency":
        self.call_value = self.value + value
        return self


def test_callable_class_instance_scoped():
    container = Container()
    with container.enter_global_scope("app"):
        solved = container.solve(Dependant(ScopedDependency.__call__))
        d1 = container.execute_sync(solved)
        assert d1.call_value == 3
        d1.value = 10
        d2 = container.execute_sync(solved)
        assert d2 is d1
        assert d2.call_value == 12
