from di.api.solved import SolvedDependant
from di.container import Container
from di.dependant import Dependant
from di.executors import SyncExecutor


# Framework code
class Request:
    ...


def web_framework():
    container = Container()
    solved = container.solve(Dependant(controller, scope="request"), scopes=["request"])
    assert isinstance(solved, SolvedDependant)

    with container.enter_scope("request") as state:
        container.execute_sync(
            solved, values={Request: Request()}, executor=SyncExecutor(), state=state
        )

    dependencies = solved.dag.keys() - {solved.dependency}
    assert all(isinstance(item, Dependant) for item in dependencies)
    assert set(dependant.call for dependant in dependencies) == {Request, MyClass}


# User code
class MyClass:
    ...


def controller(request: Request, myobj: MyClass) -> None:
    ...
