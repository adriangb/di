import inspect
from typing import Any, Mapping, Optional

from di import Container, Dependant, Depends


class Request:
    def __init__(self, headers: Mapping[str, str]) -> None:
        self.headers = {k.lower(): v for k, v in headers.items()}


class HeaderDependant(Dependant[Any]):
    def __init__(self, alias: Optional[str]) -> None:
        self.alias = alias
        super().__init__(call=None, scope=None, share=False)

    def register_parameter(self, param: inspect.Parameter) -> None:
        if self.alias is not None:
            name = self.alias
        else:
            name = param.name.replace("_", "-")

        def get_header(request: Request = Depends()) -> str:
            return param.annotation(request.headers[name])

        self.call = get_header


def Header(alias: Optional[str] = None) -> Any:
    return HeaderDependant(alias=alias)  # type: ignore


async def web_framework() -> None:
    container = Container()

    valid_request = Request(headers={"x-header-one": "one", "x-header-two": "2"})
    with container.bind(Dependant(lambda: valid_request), Request):
        await container.execute_async(container.solve(Dependant(controller)))  # success

    invalid_request = Request(headers={"x-header-one": "one"})
    with container.bind(Dependant(lambda: invalid_request), Request):
        try:
            await container.execute_async(
                container.solve(Dependant(controller))
            )  # fails
        except KeyError:
            pass
        else:
            raise AssertionError(
                "This call should have failed because x-header-two is missing"
            )


def controller(
    x_header_one: str = Header(), header_two_val: int = Header(alias="x-header-two")
) -> None:
    """This is the only piece of user code"""
    assert x_header_one == "one"
    assert header_two_val == 2
