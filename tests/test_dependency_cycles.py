"""Tested only when using Annotated since it's impossible to create a cycle using default values"""
import sys

if sys.version_info < (3, 9):
    from typing_extensions import Annotated
else:
    from typing import Annotated

import pytest

from di import Container, Dependant, Marker
from di.exceptions import DependencyCycleError


# These methods need to be defined at the global scope for
# forward references to be resolved correctly at runtime
def dep1(v: "Annotated[int, Marker(dep2)]") -> None:  # type: ignore
    ...  # pragma: no cover


def dep2(v: "Annotated[int, Marker(dep1)]") -> None:
    ...  # pragma: no cover


def test_cycle() -> None:
    container = Container()
    with container.enter_scope(None):
        with pytest.raises(DependencyCycleError, match="Nodes are in a cycle"):
            container.solve(Dependant(dep1))
