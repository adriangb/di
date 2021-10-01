from random import random

from di import Container, Dependant, Depends


def controller(
    v1: object,  # no marker is equivalent to Depends(object)
    v2: object = Depends(object),  # the default value is share=True
    v3: float = Depends(random, share=False),  # but you can set share=False
) -> None:
    assert v1 is v2
    assert v1 is not v3 and v2 is not v3


def main() -> None:
    container = Container()
    container.execute_sync(container.solve(Dependant(controller)))
