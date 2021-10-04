import sys

import pytest

from di import Container, Dependant, Depends  # noqa


def return_one() -> int:
    return 1


@pytest.mark.skipif(
    sys.version_info < (3, 8), reason="3.7 does not support positional only args"
)
def test_positional_only_parameters():
    # avoid a syntax error in 3.7, which does not support /
    return_two_def = (
        r"def return_two(one: int = Depends(return_one), /) -> int:  return one + 1"
    )
    exec(return_two_def, globals())

    container = Container()
    res = container.execute_sync(container.solve(Dependant(return_two)))  # type: ignore # noqa
    assert res == 2
