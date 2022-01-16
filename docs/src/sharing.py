from random import random

from di import Container, Dependant, SyncExecutor
from di.typing import Annotated


def controller(
    # no marker is equivalent to Dependant(object)
    v1: object,
    # the default value is share=True
    v2: Annotated[object, Dependant(object, scope="request")],
    # but you can set share=False
    v3: Annotated[float, Dependant(random, share=False, scope="request")],
) -> None:
    assert v1 is v2
    assert v1 is not v3 and v2 is not v3


def main() -> None:
    container = Container(scopes=["request"])
    solved = container.solve(Dependant(controller, scope="request"))
    with container.enter_scope("request"):
        container.execute_sync(solved, executor=SyncExecutor())
