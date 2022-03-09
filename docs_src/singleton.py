import inspect

from di.container import Container
from di.dependant import Dependant
from di.executors import SyncExecutor


class UsersRepo:
    @classmethod
    def __di_dependency__(cls, param: inspect.Parameter) -> "Dependant[UsersRepo]":
        return Dependant(UsersRepo, scope="app")


def endpoint(repo: UsersRepo) -> UsersRepo:
    return repo


def framework():
    container = Container()
    solved = container.solve(
        Dependant(endpoint, scope="request"), scopes=["app", "request"]
    )
    executor = SyncExecutor()
    with container.enter_scope("app") as app_state:
        with container.enter_scope("request", state=app_state) as req_state:
            repo1 = container.execute_sync(solved, executor=executor, state=req_state)
        with container.enter_scope("request", state=app_state) as req_state:
            repo2 = container.execute_sync(solved, executor=executor, state=req_state)
        assert repo1 is repo2
