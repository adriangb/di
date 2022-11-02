from di.api.solved import SolvedDependent
from di.container import Container
from di.dependent import Dependent
from di.executors import SyncExecutor


# Framework code
class Request:
    ...


def web_framework():
    container = Container()
    solved = container.solve(Dependent(controller, scope="request"), scopes=["request"])
    assert isinstance(solved, SolvedDependent)

    with container.enter_scope("request") as state:
        container.execute_sync(
            solved, values={Request: Request()}, executor=SyncExecutor(), state=state
        )

    dependencies = solved.dag.keys() - {solved.dependency}
    assert all(isinstance(item, Dependent) for item in dependencies)
    assert set(dependent.call for dependent in dependencies) == {Request, MyClass}


# User code
class MyClass:
    ...


def controller(request: Request, myobj: MyClass) -> None:
    ...
