import inspect
import typing
from dataclasses import dataclass

from di.api.dependencies import DependentBase
from di.container import Container
from di.dependent import Dependent
from di.executors import SyncExecutor


@dataclass
class Foo:
    bar: str = "bar"


def match_by_parameter_name(
    param: typing.Optional[inspect.Parameter], dependent: DependentBase[typing.Any]
) -> typing.Optional[DependentBase[typing.Any]]:
    if param is not None and param.name == "bar":
        return Dependent(lambda: "baz", scope=None)
    return None


container = Container()

container.bind(match_by_parameter_name)

solved = container.solve(Dependent(Foo, scope=None), scopes=[None])


def main():
    with container.enter_scope(None) as state:
        foo = container.execute_sync(solved, executor=SyncExecutor(), state=state)
    assert foo.bar == "baz"
