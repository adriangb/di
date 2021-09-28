from random import random

from di import Container, Dependant, Depends


def controller(
    v1: object,  # no marker is equivalent to Depends(object)
    v2: object = Depends(object),  # the default value is shared=True
    v3: float = Depends(random, shared=False),  # but you can set shared=False
) -> None:
    assert v1 is v2
    assert v1 is not v3 and v2 is not v3


async def main() -> None:
    container = Container()
    await container.execute(Dependant(controller))
