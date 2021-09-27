import inspect
from typing import Any, Callable, Mapping, Optional

from di import Container, Dependant
from di.params import Depends


class Request:
    def __init__(self, headers: Mapping[str, str]) -> None:
        self.headers = {k.lower(): v for k, v in headers.items()}


class HeaderDependant(Dependant[Any]):
    def __init__(self, alias: Optional[str]) -> None:
        self.alias = alias
        super().__init__(call=None, scope=None, shared=False)

    def infer_call_from_annotation(
        self, param: inspect.Parameter
    ) -> Callable[[Request], Any]:
        if self.alias is not None:
            name = self.alias
        else:
            name = param.name.replace("_", "-")

        def get_header(request: Request = Depends()) -> str:
            return param.annotation(request.headers[name])

        return get_header


def Header(alias: Optional[str] = None) -> Any:
    return HeaderDependant(alias=alias)  # type: ignore


async def web_framework() -> None:
    container = Container()

    valid_request = Request(headers={"x-header-one": "one", "x-header-two": "2"})
    with container.bind(Dependant(lambda: valid_request), Request, scope=None):
        await container.execute(Dependant(controller))  # success


def controller(
    x_header_one: str = Header(), header_two_val: int = Header(alias="x-header-two")
) -> None:
    """This is the only piece of user code"""
    assert x_header_one == "one"
    assert header_two_val == 2
