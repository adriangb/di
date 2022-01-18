from __future__ import annotations

import inspect
from typing import Any, Mapping, Optional, TypeVar

from di import AsyncExecutor, Container, Dependant
from di.typing import Annotated


class Request:
    def __init__(self, headers: Mapping[str, str]) -> None:
        self.headers = {k.lower(): v for k, v in headers.items()}


class Header(Dependant[Any]):
    def __init__(self, alias: Optional[str]) -> None:
        self.alias = alias
        super().__init__(call=None, scope="request", share=False)

    def register_parameter(self, param: inspect.Parameter) -> Header:
        if self.alias is not None:
            name = self.alias
        else:
            name = param.name.replace("_", "-")

        def get_header(request: Annotated[Request, Dependant()]) -> str:
            return param.annotation(request.headers[name])

        self.call = get_header
        # We could return a copy here to allow the same Dependant
        # to be used in multiple places like
        # dep = HeaderDependant(...)
        # def func1(abcd = dep): ...
        # def func2(efgh = dep): ...
        # In this scenario, `dep` would be modified in func2 to set
        # the header name to "efgh", which leads to incorrect results in func1
        # The solution is to return a copy here instead of self, so that
        # the original instance is never modified in place
        return self


T = TypeVar("T")

FromHeader = Annotated[T, Header(alias=None)]


async def web_framework() -> None:
    container = Container(scopes=["request"])

    valid_request = Request(headers={"x-header-one": "one", "x-header-two": "2"})
    with container.register_by_type(
        Dependant(lambda: valid_request, scope="request"), Request
    ):
        solved = container.solve(Dependant(controller, scope="request"))
    with container.enter_scope("request"):
        await container.execute_async(solved, executor=AsyncExecutor())  # success

    invalid_request = Request(headers={"x-header-one": "one"})
    with container.register_by_type(
        Dependant(lambda: invalid_request, scope="request"), Request
    ):
        solved = container.solve(Dependant(controller, scope="request"))

    with container.enter_scope("request"):
        try:
            await container.execute_async(solved, executor=AsyncExecutor())  # fails
        except KeyError:
            pass
        else:
            raise AssertionError(
                "This call should have failed because x-header-two is missing"
            )


def controller(
    x_header_one: FromHeader[str],
    header_two_val: Annotated[int, Header(alias="x-header-two")],
) -> None:
    """This is the only piece of user code"""
    assert x_header_one == "one"
    assert header_two_val == 2
