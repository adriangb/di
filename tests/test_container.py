from typing import Type, Union

import pytest

from di import Container
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
