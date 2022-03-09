from di.container import Container
from di.dependant import Dependant
from di.executors import SyncExecutor


class Foo:
    called: bool = False

    def foo(self: "Foo") -> "Foo":
        self.called = True
        return self


def test_forward_ref_evalutation():
    container = Container()
    with container.enter_scope(None) as state:
        res = container.execute_sync(
            container.solve(Dependant(Foo.foo), scopes=[None]),
            executor=SyncExecutor(),
            state=state,
        )
    assert isinstance(res, Foo)
    assert res.called
