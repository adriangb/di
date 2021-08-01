import pytest

from anydep.container import Container
from anydep.exceptions import DuplicateScopeError, UnknownScopeError
from anydep.models import Dependant
from anydep.params import Depends


class Dep:
    def __init__(self) -> None:
        self.value: int = 0

    def __call__(self) -> int:
        return self.value


dep1 = Dep()
dep2 = Dep()


def app_scoped(v: int = Depends(dep1, scope="app")):
    return v


def request_scoped(v: int = Depends(dep1, scope="request")):
    return v


def no_scope(v: int = Depends(dep1, scope=False)):
    return v


def default_scope(v: int = Depends(dep1, scope=None)):
    return v


@pytest.mark.anyio
async def test_scoped():
    container = Container()
    for d in (dep1, app_scoped):
        async with container.enter_global_scope("app"):
            dep1.value = 1
            r = await container.execute(Dependant(d))
            assert r == 1, d
            dep1.value = 2
            r = await container.execute(Dependant(d))
            assert r == 1, d  # unchanged


@pytest.mark.anyio
async def test_transient():
    container = Container()
    async with container.enter_global_scope("app"):
        dep1.value = 1
        r = await container.execute(Dependant(app_scoped))
        assert r == 1
        dep1.value = 2
        r = await container.execute(Dependant(no_scope))
        assert r == 2  # not cached


@pytest.mark.anyio
async def test_unknown_scope():
    def bad_dep(v: int = Depends(dep1, scope="abcde")) -> int:
        return v

    container = Container()
    async with container.enter_global_scope("app"):
        with pytest.raises(UnknownScopeError):
            await container.execute(Dependant(bad_dep))


@pytest.mark.anyio
async def test_no_scopes():
    def bad_dep(v: int = Depends(dep1, scope="abcde")) -> int:
        return v

    container = Container()
    with pytest.raises(UnknownScopeError):
        await container.execute(Dependant(bad_dep))


@pytest.mark.anyio
async def test_duplicate_scope():

    container = Container()
    async with container.enter_global_scope("app"):
        with pytest.raises(DuplicateScopeError):
            async with container.enter_global_scope("app"):
                ...


@pytest.mark.anyio
async def test_nested_scopes():
    container = Container()
    async with container.enter_global_scope("app"):
        dep1.value = 1
        r = await container.execute(Dependant(app_scoped))
        assert r == 1
        dep1.value = 2
        async with container.enter_local_scope("request"):
            dep1.value = 2
            r = await container.execute(Dependant(request_scoped))
            assert r == 1  # cached from app scope
            r = await container.execute(Dependant(no_scope))
            assert r == 2  # not cached


@pytest.mark.anyio
async def test_nested_caching():
    container = Container()
    async with container.enter_global_scope("app"):
        async with container.enter_local_scope("request"):
            dep1.value = 1
            r = await container.execute(Dependant(request_scoped))
            assert r == 1
            dep1.value = 2
            r = await container.execute(Dependant(app_scoped))
            assert r == 1  # uses the request scoped cache
        r = await container.execute(Dependant(app_scoped))
        assert r == 2  # not cached anymore


@pytest.mark.anyio
async def test_nested_caching_outlive():
    def app_scoped(v: int = Depends(dep1, scope="app")):
        return v

    def request_scoped(v: int = Depends(dep2, scope="request")):
        return v

    container = Container()
    async with container.enter_global_scope("app"):
        async with container.enter_local_scope("request"):
            dep1.value = 1
            dep2.value = 1
            # since dep hasn't been cached yet, it gets cached
            # because it is marked as app scoped, it gets cached in the app scope
            # even if it is first initialized in a request scope
            r = await container.execute(Dependant(app_scoped))
            assert r == 1
            r = await container.execute(Dependant(request_scoped))
            assert r == 1
        dep1.value = 2
        dep2.value = 2
        r = await container.execute(Dependant(app_scoped))
        assert r == 1  # still cached because it's app scoped
        async with container.enter_local_scope("request"):
            r = await container.execute(Dependant(request_scoped))
            assert r == 2  # not cached anymore since we're in a different request scope
