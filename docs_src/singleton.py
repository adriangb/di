import inspect

from di import Container
from di.dependent import Dependent
from di.executors import SyncExecutor


class UsersRepo:
    @classmethod
    def __di_dependency__(cls, param: inspect.Parameter) -> "Dependent[UsersRepo]":
        return Dependent(UsersRepo, scope="app")


def endpoint(repo: UsersRepo) -> UsersRepo:
    return repo


def framework():
    container = Container()
    solved = container.solve(
        Dependent(endpoint, scope="request"), scopes=["app", "request"]
    )
    executor = SyncExecutor()
    with container.enter_scope("app") as app_state:
        with container.enter_scope("request", state=app_state) as req_state:
            repo1 = solved.execute_sync(executor=executor, state=req_state)
        with container.enter_scope("request", state=app_state) as req_state:
            repo2 = solved.execute_sync(executor=executor, state=req_state)
        assert repo1 is repo2
