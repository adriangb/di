from random import random

from di import Container, Dependant, Depends


def controller(
    v1: object,  # no marker is equivalent to Depends(object)
    v2: object = Depends(object, scope="request"),  # the default value is share=True
    v3: float = Depends(
        random, share=False, scope="request"
    ),  # but you can set share=False
) -> None:
    assert v1 is v2
    assert v1 is not v3 and v2 is not v3


def main() -> None:
    container = Container(scopes=["request"])
    solved = container.solve(Dependant(controller, scope="request"))
    with container.enter_scope("request"):
        container.execute_sync(solved)
