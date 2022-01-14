from di import Container, Dependant
from di.api.solved import SolvedDependant


# Framework code
class Request:
    ...


def web_framework():
    container = Container(scopes=["request"])
    solved = container.solve(Dependant(controller, scope="request"))
    assert isinstance(solved, SolvedDependant)

    with container.enter_scope("request"):
        container.execute_sync(solved, values={Request: Request()})

    dependencies = solved.get_flat_subdependants()
    assert all(isinstance(item, Dependant) for item in dependencies)
    assert set(dependant.call for dependant in dependencies) == {Request, MyClass}


# User code
class MyClass:
    ...


def controller(request: Request, myobj: MyClass) -> None:
    ...
