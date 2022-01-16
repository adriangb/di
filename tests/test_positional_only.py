import sys

import pytest

from di import Container, Dependant, SyncExecutor


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

    container = Container(scopes=(None,))
    solved = container.solve(Dependant(func))
    with container.enter_scope(None):
        container.execute_sync(solved, executor=SyncExecutor())
