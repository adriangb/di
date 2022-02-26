from di import Container, Dependant, SyncExecutor
from di.dependant import Injectable


class UsersRepo(Injectable, scope="singleton"):
    pass


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
