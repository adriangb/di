import inspect
from typing import Mapping, Optional, TypeVar

from di import Container, bind_by_type
from di.dependent import Dependent, Marker
from di.executors import AsyncExecutor
from di.typing import Annotated


class Request:
    def __init__(self, headers: Mapping[str, str]) -> None:
        self.headers = {k.lower(): v for k, v in headers.items()}


class Header(Marker):
    def __init__(self, alias: Optional[str]) -> None:
        self.alias = alias
        super().__init__(call=None, scope="request", use_cache=False)

    def register_parameter(self, param: inspect.Parameter) -> Dependent[str]:
        if self.alias is not None:
            name = self.alias
        else:
            name = param.name.replace("_", "-")

        def get_header(request: Annotated[Request, Marker()]) -> str:
            return param.annotation(request.headers[name])

        return Dependent(get_header, scope="request")


T = TypeVar("T")

FromHeader = Annotated[T, Header(alias=None)]


async def web_framework() -> None:
    container = Container()

    valid_request = Request(headers={"x-header-one": "one", "x-header-two": "2"})
    with container.bind(
        bind_by_type(Dependent(lambda: valid_request, scope="request"), Request)
    ):
        solved = container.solve(
            Dependent(controller, scope="request"), scopes=["request"]
        )
    with container.enter_scope("request") as state:
        await solved.execute_async(executor=AsyncExecutor(), state=state)  # success

    invalid_request = Request(headers={"x-header-one": "one"})
    with container.bind(
        bind_by_type(Dependent(lambda: invalid_request, scope="request"), Request)
    ):
        solved = container.solve(
            Dependent(controller, scope="request"), scopes=["request"]
        )

    with container.enter_scope("request") as state:
        try:
            await solved.execute_async(executor=AsyncExecutor(), state=state)  # fails
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
