from typing import Callable, Dict, Literal

import pytest

from di import Container, Dependant, Depends
from di.exceptions import DependencyRegistryError, ScopeViolationError, WiringError


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
        match="Dependencies may not use variable positional or keyword arguments",
    ):
        container.execute_sync(container.solve(Dependant(args_func)))
    with pytest.raises(
        WiringError,
        match="Dependencies may not use variable positional or keyword arguments",
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
            match = r"dependency in two different scopes"
            with pytest.raises(DependencyRegistryError, match=match):
                container.execute_sync(container.solve(Dependant(D)))
