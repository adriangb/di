from typing import Generator, Type, Union

import pytest

from di import Container, Dependant
from di.api.container import ContainerProtocol
from di.container import BaseContainer


def test_execution_scope() -> None:
    def dep() -> Generator[int, None, None]:
        yield 1

    container = Container(execution_scope=1234)

    res = container.execute_sync(container.solve(Dependant(dep, scope=1234)))
    assert res == 1


@pytest.mark.parametrize("container_cls", [BaseContainer, Container])
def test_scopes_property(container_cls: Type[ContainerProtocol]) -> None:
    container = container_cls()
    assert list(container.scopes) == []
    with container.enter_scope("test") as container:
        assert list(container.scopes) == ["test"]
        with container.enter_scope("another") as container:
            assert list(container.scopes) == ["test", "another"]


class BaseContainerSubclass(BaseContainer):
    pass


class ContainerSubclass(Container):
    pass


@pytest.mark.parametrize("container_cls", [ContainerSubclass, BaseContainerSubclass])
def test_enter_scope_subclass(
    container_cls: Union[Type[ContainerSubclass], Type[BaseContainerSubclass]]
) -> None:

    container = container_cls()
    assert list(container.scopes) == []
    with container.enter_scope("test") as container:
        assert isinstance(container, container_cls)
        assert list(container.scopes) == ["test"]
        with container.enter_scope("another") as container:
            assert isinstance(container, container_cls)
            assert list(container.scopes) == ["test", "another"]


def test_binds_property():
    container = Container()
    assert container.binds == {}

    def func() -> None:
        ...

    dep = Dependant(lambda: None)
    container.bind(dep, func)
    assert container.binds == {func: dep}


@pytest.mark.parametrize(
    "container_cls",
    [BaseContainer, Container, BaseContainerSubclass, ContainerSubclass],
)
def test_container_api(
    container_cls: Union[
        Type[BaseContainer],
        Type[Container],
        Type[BaseContainerSubclass],
        Type[ContainerSubclass],
    ]
) -> None:
    """Check to make sure the container implementations comply w/ the API."""
    x: ContainerProtocol
    # mypy will throw an error here if the API is not implemented correctly
    x = container_cls()
    x = x
