from typing import Type, Union

import pytest

from di import Container
from di.container import BaseContainer


@pytest.mark.parametrize("container_cls", [BaseContainer, Container])
def test_current_scopes_property(
    container_cls: Union[Type[BaseContainer], Type[Container]]
) -> None:
    container = container_cls(scopes=("test", "another"))
    assert list(container.current_scopes) == []
    with container.enter_scope("test") as container:
        assert list(container.current_scopes) == ["test"]
        with container.enter_scope("another") as container:
            assert list(container.current_scopes) == ["test", "another"]


@pytest.mark.parametrize("container_cls", [BaseContainer, Container])
def test_scopes_property(
    container_cls: Union[Type[BaseContainer], Type[Container]]
) -> None:
    container = container_cls(scopes=("test", "another"))
    assert list(container.scopes) == ["test", "another"]


class BaseContainerSubclass(BaseContainer):
    pass


class ContainerSubclass(Container):
    pass


def test_enter_scope_container_subclass() -> None:
    container = ContainerSubclass(scopes=("test", "another"))
    assert list(container.current_scopes) == []
    with container.enter_scope("test") as container:
        assert isinstance(container, ContainerSubclass)
        assert list(container.current_scopes) == ["test"]
        with container.enter_scope("another") as container:
            assert isinstance(container, ContainerSubclass)
            assert list(container.current_scopes) == ["test", "another"]


def test_enter_scope_base_container_subclass() -> None:
    container = BaseContainerSubclass(scopes=("test", "another"))
    assert list(container.current_scopes) == []
    with container.enter_scope("test") as container:
        assert isinstance(container, BaseContainerSubclass)
        assert list(container.current_scopes) == ["test"]
        with container.enter_scope("another") as container:
            assert isinstance(container, BaseContainerSubclass)
            assert list(container.current_scopes) == ["test", "another"]
