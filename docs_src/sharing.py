from random import random

from di.container import Container
from di.dependant import Dependant, Marker
from di.executors import SyncExecutor
from di.typing import Annotated


def controller(
    # no marker is equivalent to Dependant(object)
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
    solved = container.solve(Dependant(controller, scope="request"), scopes=["request"])
    with container.enter_scope("request") as state:
        container.execute_sync(solved, executor=SyncExecutor(), state=state)
