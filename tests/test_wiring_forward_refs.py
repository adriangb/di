from di import Container, Dependant, SyncExecutor


class Foo:
    called: bool = False

    def foo(self: "Foo") -> "Foo":
        self.called = True
        return self


def test_forward_ref_evalutation():
    container = Container(scopes=(None,))
    with container.enter_scope(None):
        res = container.execute_sync(
            container.solve(Dependant(Foo.foo)), executor=SyncExecutor()
        )
    assert isinstance(res, Foo)
    assert res.called
