from random import random

from di import Container
from di.dependent import Dependent, Marker
from di.executors import SyncExecutor
from di.typing import Annotated


def controller(
    # no marker is equivalent to Dependent(object)
    v1: object,
    # the default value is use_cache=True
    v2: Annotated[object, Marker(object, scope="request")],
    # but you can set use_cache=False
    v3: Annotated[float, Marker(random, use_cache=False, scope="request")],
) -> None:
    assert v1 is v2
    assert v1 is not v3 and v2 is not v3


def main() -> None:
    container = Container()
    solved = container.solve(Dependent(controller, scope="request"), scopes=["request"])
    with container.enter_scope("request") as state:
        solved.execute_sync(executor=SyncExecutor(), state=state)
