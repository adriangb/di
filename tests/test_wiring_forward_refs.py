from di import Container, Dependant


class Foo:
    called: bool = False

    def foo(self: "Foo") -> "Foo":
        self.called = True
        return self


def test_forward_ref_evalutation():
    container = Container(scopes=(None,))
    with container.enter_scope(None):
        res = container.execute_sync(container.solve(Dependant(Foo.foo)))
    assert isinstance(res, Foo)
    assert res.called
