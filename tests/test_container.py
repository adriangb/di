from typing import Type, Union

import pytest

from di import Container
from di.container import BaseContainer


class BaseContainerSubclass(BaseContainer):
    pass


class ContainerSubclass(Container):
    pass


@pytest.mark.parametrize(
    "container_cls",
    [BaseContainer, Container, BaseContainerSubclass, ContainerSubclass],
)
def test_current_scopes_property(
    container_cls: Union[Type[BaseContainer], Type[Container]]
) -> None:
    container = container_cls()
    assert list(container.state.scopes) == []
    with container.enter_scope("test") as container:
        assert list(container.state.scopes) == ["test"]
        with container.enter_scope("another") as container:
            assert list(container.state.scopes) == ["test", "another"]
