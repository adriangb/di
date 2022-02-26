import inspect

from di import Container, Dependant, SyncExecutor


class UsersRepo:
    @classmethod
    def __di_dependency__(cls, param: inspect.Parameter) -> "Dependant[UsersRepo]":
        return Dependant(UsersRepo, scope="singleton")


def endpoint(repo: UsersRepo) -> UsersRepo:
    return repo


def framework():
    container = Container(scopes=["singleton", "request"])
    solved = container.solve(Dependant(endpoint, scope="request"))
    executor = SyncExecutor()
    with container.enter_scope("singleton"):
        with container.enter_scope("request"):
            repo1 = container.execute_sync(solved, executor=executor)
        with container.enter_scope("request"):
            repo2 = container.execute_sync(solved, executor=executor)
        assert repo1 is repo2
