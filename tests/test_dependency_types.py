import pytest

from anydep.container import Container
from anydep.models import Dependant
from tests.dependencies import (
    AsyncCMClass,
    SyncCMClass,
    async_call,
    async_callable_class,
    async_gen,
    callable_class,
    counter,
    lifetimes,
    sync_call,
    sync_gen,
)


@pytest.mark.parametrize(
    "dep",
    [
        AsyncCMClass,
        async_gen,
        SyncCMClass,
        sync_gen,
    ],
)
@pytest.mark.anyio
async def test_context_manager_dependency_execution(dep) -> None:
    container = Container()
    async with container.enter_global_scope("app"):
        assert counter.get(dep, None) is None
        assert lifetimes.get(dep, None) is None
        await container.execute(Dependant(dep))
        assert lifetimes[dep] == "started"
        assert counter[dep] == 1
    assert lifetimes[dep] == "finished"


@pytest.mark.parametrize(
    "dep",
    [
        async_call,
        async_callable_class,
        sync_call,
        callable_class,
    ],
)
@pytest.mark.anyio
async def test_callable_dependency_execution(dep) -> None:
    container = Container()
    async with container.enter_global_scope("app"):
        assert counter.get(dep, None) is None
        await container.execute(Dependant(dep))
        assert counter[dep] == 1
