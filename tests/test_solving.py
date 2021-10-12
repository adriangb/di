import sys
from typing import Any, Callable, Dict, List

if sys.version_info < (3, 8):
    from typing_extensions import Literal
else:
    from typing import Literal

import pytest

from di import Container, Dependant, Depends
from di.exceptions import DependencyRegistryError, ScopeViolationError, WiringError
from di.types.dependencies import DependantProtocol, DependencyParameter


def test_no_annotations():
    """Dependencies must provide annotations or a default value"""

    def badfunc(value):  # type: ignore
        ...

    container = Container()

    with pytest.raises(
        WiringError,
        match="Cannot wire a parameter with no default and no type annotation",
    ):
        container.execute_sync(container.solve(Dependant(badfunc)))  # type: ignore


def test_variable_arguments():
    """Dependencies cannot use *args or **kwargs, even with type annotations"""

    def args_func(*args: str):
        ...

    def kwargs_func(**kwargs: Dict[str, str]):
        ...

    container = Container()

    with pytest.raises(
        WiringError,
        match="^Dependencies may not use variable positional or keyword arguments$",
    ):
        container.execute_sync(container.solve(Dependant(args_func)))
    with pytest.raises(
        WiringError,
        match="^Dependencies may not use variable positional or keyword arguments$",
    ):
        container.execute_sync(container.solve(Dependant(kwargs_func)))


def test_default_argument():
    """No type annotations are required if default values are provided"""

    def default_func(value=2) -> int:  # type: ignore
        return value  # type: ignore

    container = Container()

    res = container.execute_sync(container.solve(Dependant(default_func)))  # type: ignore
    assert res == 2


def test_invalid_non_callable_annotation():
    """The type annotation value: int is not a valid identifier since 1 is not a callable"""

    def func(value: 1 = Depends()) -> int:  # type: ignore
        return value

    container = Container()

    match = "Annotation for value is not a callable class or function"
    with pytest.raises(WiringError, match=match):
        container.execute_sync(container.solve(Dependant(func)))


def func1(value: Literal[1] = Depends()) -> int:
    return value


def func2(value: int = Depends()) -> int:
    return value


@pytest.mark.parametrize("function, annotation", [(func1, Literal[1]), (func2, int)])
def test_valid_non_callable_annotation(
    function: Callable[[int], int], annotation: type
):
    """No type annotations are required if default values are provided"""

    container = Container()
    container.bind(Dependant(lambda: 1), annotation)
    res = container.execute_sync(container.solve(Dependant(function)))
    assert res == 1


def test_dissalow_depending_on_inner_scope():
    """A dependency cannot depend on sub-dependencies that are scoped to a narrower scope"""

    def A() -> None:
        ...

    def B(a: None = Depends(A, scope="inner")):
        ...

    container = Container()
    with container.enter_local_scope("outer"):
        with container.enter_local_scope("inner"):
            match = r"scope \(inner\) is narrower than .+'s scope \(outer\)"
            with pytest.raises(ScopeViolationError, match=match):
                container.execute_sync(container.solve(Dependant(B, scope="outer")))


def test_dependency_with_multiple_scopes():
    def A() -> None:
        ...

    def B(a: None = Depends(A, scope="app")):
        ...

    def C(a: None = Depends(A, scope="request")):
        ...

    def D(b: None = Depends(B), c: None = Depends(C)):
        ...

    container = Container()
    with container.enter_local_scope("app"):
        with container.enter_local_scope("request"):
            match = r"have the same lookup \(__hash__ and __eq__\) but have different scopes"
            with pytest.raises(DependencyRegistryError, match=match):
                container.execute_sync(container.solve(Dependant(D)))


def test_siblings() -> None:
    class DepOne:
        calls: int = 0

        def __call__(self) -> int:
            self.calls += 1
            return 1

    dep1 = DepOne()

    class Sibling:
        called = False

        def __call__(self, one: int = Depends(dep1)) -> None:
            assert one == 1
            self.called = True

    def dep2(one: int = Depends(dep1)) -> int:
        return one + 1

    container = Container()

    siblings = [Sibling(), Sibling()]
    solved = container.solve(Dependant(dep2), siblings=[Dependant(s) for s in siblings])
    container.execute_sync(solved)
    assert all(s.called for s in siblings)
    assert dep1.calls == 1  # they all shared the dependency


def test_non_parameter_dependency():
    """Dependencies can be declared as not call parameters but rather just computationally required"""

    calls: List[bool] = []

    class CustomDependant(Dependant[None]):
        called: bool = False

        def gather_dependencies(
            self,
        ) -> List[DependencyParameter[DependantProtocol[Any]]]:
            return [
                DependencyParameter(Dependant(call=lambda: calls.append(True)), None)
            ]

    container = Container()

    dep = CustomDependant(lambda: None)
    container.execute_sync(container.solve(dep))  # type: ignore
    assert calls == [True]


class CannotBeWired:
    # cannot be autowired because of *args, **kwargs
    def __init__(self, *args, **kwargs) -> None:
        ...


def test_no_autowire() -> None:
    """Specifying autowire=False skips autowiring non explicit sub dependencies"""

    def collect(bad: CannotBeWired) -> None:
        ...

    container = Container()
    container.solve(Dependant(collect, autowire=False))


def test_no_wire() -> None:
    """Specifying wire=False skips wiring on the dependency itself"""

    container = Container()
    container.solve(Dependant(CannotBeWired, wire=False))
