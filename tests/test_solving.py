from typing import Dict

import pytest

from di import Container, Dependant
from di.exceptions import WiringError


@pytest.mark.anyio
async def test_no_annotations():
    """Dependencies must provide annotations or a default value"""

    def badfunc(value):  # type: ignore
        ...

    container = Container()

    with pytest.raises(
        WiringError,
        match="Cannot wire a parameter with no default and no type annotation",
    ):
        await container.execute(Dependant(badfunc))  # type: ignore


@pytest.mark.anyio
async def test_variable_arguments():
    """Dependencies cannot use *args or **kwargs, even with type annotations"""

    def args_func(*args: str):
        ...

    def kwargs_func(**kwargs: Dict[str, str]):
        ...

    container = Container()

    with pytest.raises(
        WiringError,
        match="Dependencies may not use variable positional or keyword arguments",
    ):
        await container.execute(Dependant(args_func))
    with pytest.raises(
        WiringError,
        match="Dependencies may not use variable positional or keyword arguments",
    ):
        await container.execute(Dependant(kwargs_func))


@pytest.mark.anyio
async def test_default_argument():
    """No type annotations are required if default values are provided"""

    def default_func(value=2) -> int:  # type: ignore
        return value  # type: ignore

    container = Container()

    res = await container.execute(Dependant(default_func))  # type: ignore
    assert res == 2
