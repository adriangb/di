from typing import Any, Iterable, List

from di import Container, Dependant
from di.types.dependencies import DependantProtocol


class Request:
    def __init__(self, scopes: Iterable[str]) -> None:
        self.scopes = set(scopes)


class SecurityDependant(Dependant[bool]):
    def __init__(self, scopes: Iterable[str]) -> None:
        self.scopes = set(scopes)
        super().__init__(call=self.__call__, scope=None, shared=False)

    async def __call__(self, request: Request) -> bool:
        return self.scopes.issubset(request.scopes)


def Security(*scopes: str) -> bool:
    return SecurityDependant(scopes)  # type: ignore


def gather_scopes(deps: List[DependantProtocol[Any]]) -> List[str]:
    scopes: List[str] = []
    for dep in deps:
        if isinstance(dep, SecurityDependant):
            scopes.extend(dep.scopes)
    return scopes


async def web_framework() -> None:
    container = Container()

    # note: we bind a placeholder request here so that autowiring does not complain
    # about not knowing how to build a Request
    with container.bind(Dependant(lambda: Request(scopes=[])), Request):
        scopes = gather_scopes(
            container.solve(Dependant(controller)).flat_subdependants
        )

    assert set(scopes) == {"scope1", "scope2"}

    valid_request = Request(scopes=["scope1", "scope2"])
    with container.bind(Dependant(lambda: valid_request), Request):
        await container.execute_async(container.solve(Dependant(controller)))  # success

    invalid_request = Request(scopes=["scope1"])
    with container.bind(Dependant(lambda: invalid_request), Request):
        try:
            await container.execute_async(
                container.solve(Dependant(controller))
            )  # fails
        except ValueError:
            pass
        else:
            raise AssertionError("Using a request without the right scopes should fail")


def controller(authenticated: bool = Security("scope1", "scope2")) -> None:
    """This is the only piece of user code"""
    if not authenticated:
        raise ValueError
