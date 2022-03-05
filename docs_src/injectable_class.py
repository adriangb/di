from di import Container, Dependant, SyncExecutor
from di.dependant import Injectable


class UsersRepo(Injectable, scope="app"):
    pass


def endpoint(repo: UsersRepo) -> UsersRepo:
    return repo


def framework():
    container = Container()
    solved = container.solve(
        Dependant(endpoint, scope="request"), scopes=["app", "request"]
    )
    executor = SyncExecutor()
    with container.enter_scope("app") as app_state:
        with container.enter_scope("request", state=app_state) as request_state:
            repo1 = container.execute_sync(
                solved, executor=executor, state=request_state
            )
        with container.enter_scope("request"):
            repo2 = container.execute_sync(
                solved, executor=executor, state=request_state
            )
        assert repo1 is repo2
