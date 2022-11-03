from dataclasses import dataclass

from di.container import Container
from di.dependent import Dependent
from di.executors import SyncExecutor


class A:
    ...


class B:
    ...


@dataclass
class C:
    a: A
    b: B


def main():
    container = Container()
    solved = container.solve(Dependent(C, scope="request"), scopes=["request"])
    with container.enter_scope("request") as state:
        c = container.execute_sync(solved, executor=SyncExecutor(), state=state)
    assert isinstance(c, C)
    assert isinstance(c.a, A)
    assert isinstance(c.b, B)
