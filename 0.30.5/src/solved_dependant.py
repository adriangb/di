from di import Container, Dependant
from di.api.solved import SolvedDependant


# Framework code
class Request:
    ...


def web_framework():
    container = Container()
    solved = container.solve(Dependant(controller))
    assert isinstance(solved, SolvedDependant)

    container.execute_sync(solved, values={Request: Request()})

    dependencies = solved.get_flat_subdependants()
    assert all(isinstance(item, Dependant) for item in dependencies)
    assert set(dependant.call for dependant in dependencies) == {Request, MyClass}


# User code
class MyClass:
    ...


def controller(request: Request, myobj: MyClass) -> None:
    ...
