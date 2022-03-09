import sys

import pytest

from di.container import Container
from di.dependant import Dependant
from di.executors import SyncExecutor


class Test:
    pass


@pytest.mark.skipif(
    sys.version_info < (3, 8), reason="3.7 does not support positional only args"
)
def test_positional_only_parameters():
    def func(one: Test) -> None:
        ...

    # avoid a syntax error in 3.7, which does not support /
    func_def = r"def func(one: Test, /) -> None:  ..."
    exec(func_def, globals())

    container = Container()
    solved = container.solve(Dependant(func), scopes=[None])
    with container.enter_scope(None) as state:
        container.execute_sync(solved, executor=SyncExecutor(), state=state)
