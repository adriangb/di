"""Tested only when using Annotated since it's impossible to create a cycle using default values"""
import pytest

from di.container import Container
from di.dependant import Dependant, Marker
from di.exceptions import DependencyCycleError
from di.typing import Annotated


# These methods need to be defined at the global scope for
# forward references to be resolved correctly at runtime
def dep1(v: "Annotated[int, Marker(dep2)]") -> int:  # type: ignore
    return 1  # pragma: no cover


def dep2(v: "Annotated[int, Marker(dep1)]") -> int:
    return 2  # pragma: no cover


def test_cycle() -> None:
    container = Container()
    with container.enter_scope(None):
        with pytest.raises(DependencyCycleError, match="Nodes are in a cycle"):
            container.solve(Dependant(dep1), scopes=[None])
