"""Tested only when using Annotated since it's impossible to create a cycle using default values"""
import sys

if sys.version_info < (3, 9):
    from typing_extensions import Annotated
else:
    from typing import Annotated

import pytest

from di import Container, Dependant, Depends
from di.exceptions import DependencyCycleError


# These methods need to be defined at the global scope for
# forward references to be resolved correctly at runtime
def dep1(v: "Annotated[int, Depends(dep2)]") -> int:
    return 1


def dep2(v: "Annotated[int, Depends(dep1)]") -> int:
    return 2


def test_cycle() -> None:
    container = Container(scopes=(None,))
    msg = r"Dependant\(call=<function dep1[^)]+\) -> Dependant\(call=<function dep2[^)]+\) -> Dependant\(call=<function dep1[^)]+\)"
    with container.enter_scope(None):
        with pytest.raises(DependencyCycleError, match=msg) as errs:
            container.solve(Dependant(dep1))
    deps_in_cycle = errs.value.args[1]
    funcs_in_cylce = [d.call for d in deps_in_cycle]
    assert funcs_in_cylce in ([dep1, dep2, dep1], [dep2, dep1, dep2])
