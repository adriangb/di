from typing import Type, Union

import pytest

from di import Container
from di.api.container import ContainerProtocol
from di.container import BaseContainer


@pytest.mark.parametrize("container_cls", [BaseContainer, Container])
def test_scopes_property(
    container_cls: Union[Type[BaseContainer], Type[Container]]
) -> None:
    container = container_cls(scopes=("test", "another"))
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

    container = container_cls(scopes=("test", "another"))
    assert list(container.scopes) == []
    with container.enter_scope("test") as container:
        assert isinstance(container, container_cls)
        assert list(container.scopes) == ["test"]
        with container.enter_scope("another") as container:
            assert isinstance(container, container_cls)
            assert list(container.scopes) == ["test", "another"]


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
    x = container_cls(scopes=(None,))
    x = x  # avoid linting errors with unused variable
