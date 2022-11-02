from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, Generator

import pytest

from di.container import Container, bind_by_type
from di.dependent import Dependent, Marker
from di.executors import AsyncExecutor, SyncExecutor
from di.typing import Annotated


@dataclass
class Recorder:
    caught: Dict[str, bool] = field(default_factory=dict)


class MyException(Exception):
    ...


def dep1(rec: Recorder) -> Generator[None, None, None]:
    try:
        yield
    except MyException:
        rec.caught["dep1"] = True


def dep2(rec: Recorder) -> Generator[None, None, None]:
    try:
        yield
    except MyException:
        rec.caught["dep2"] = True


async def async_dep1(rec: Recorder) -> AsyncGenerator[None, None]:
    try:
        yield
    except MyException:
        rec.caught["async_dep1"] = True


async def async_dep2(rec: Recorder) -> AsyncGenerator[None, None]:
    try:
        yield
    except MyException:
        rec.caught["async_dep1"] = True


def test_dependency_can_catch_exception_single_sync() -> None:
    def collector(one: Annotated[None, Marker(dep1)]) -> None:
        raise MyException

    container = Container()
    rec = Recorder()
    container.bind(bind_by_type(Dependent(lambda: rec), Recorder))
    with container.enter_scope(None) as state:
        container.execute_sync(
            container.solve(Dependent(collector), scopes=[None]),
            executor=SyncExecutor(),
            state=state,
        )
    assert rec.caught == {"dep1": True}


@pytest.mark.anyio
async def test_dependency_can_catch_exception_single_async() -> None:
    def collector(one: Annotated[None, Marker(async_dep1)]) -> None:
        raise MyException

    container = Container()
    rec = Recorder()
    container.bind(bind_by_type(Dependent(lambda: rec), Recorder))
    solved = container.solve(Dependent(collector), scopes=[None])
    async with container.enter_scope(None) as state:
        await container.execute_async(
            solved,
            executor=AsyncExecutor(),
            state=state,
        )
    assert rec.caught == {"async_dep1": True}


def test_dependency_can_catch_exception_concurrent_sync() -> None:
    def collector(
        one: Annotated[None, Marker(dep1)], two: Annotated[None, Marker(dep2)]
    ) -> None:
        raise MyException

    container = Container()
    rec = Recorder()
    container.bind(bind_by_type(Dependent(lambda: rec), Recorder))
    with container.enter_scope(None) as state:
        container.execute_sync(
            container.solve(Dependent(collector), scopes=[None]),
            executor=SyncExecutor(),
            state=state,
        )
    # one of the dependencies catches and swallows the exception
    # so the other one never sees it
    # there is no promises as to the order, both cases are valid
    assert rec.caught == {"dep1": True} or rec.caught == {"dep2": True}


@pytest.mark.anyio
async def test_dependency_can_catch_exception_concurrent_async() -> None:
    def collector(
        one: Annotated[None, Marker(async_dep1)],
        two: Annotated[None, Marker(async_dep2)],
    ) -> None:
        raise MyException

    container = Container()
    rec = Recorder()
    container.bind(bind_by_type(Dependent(lambda: rec), Recorder))
    solved = container.solve(Dependent(collector), scopes=[None])
    async with container.enter_scope(None) as state:
        await container.execute_async(
            solved,
            executor=AsyncExecutor(),
            state=state,
        )
    # one of the dependencies catches and swallows the exception
    # so the other one nevers sees it
    # there is no promises as to the order, both cases are valid
    assert rec.caught == {"async_dep1": True} or rec.caught == {"async_dep2": True}


@pytest.mark.anyio
async def test_dependency_can_catch_exception_concurrent_mixed() -> None:
    def collector(
        one: Annotated[None, Marker(async_dep1)],
        two: Annotated[None, Marker(dep2)],
    ) -> None:
        raise MyException

    container = Container()
    rec = Recorder()
    container.bind(bind_by_type(Dependent(lambda: rec), Recorder))
    async with container.enter_scope(None) as state:
        await container.execute_async(
            container.solve(Dependent(collector), scopes=[None]),
            executor=AsyncExecutor(),
            state=state,
        )
    # one of the dependencies catches and swallows the exception
    # so the other one never sees it
    # there is no promises as to the order, both cases are valid
    assert rec.caught == {"async_dep1": True} or rec.caught == {"dep2": True}


def dep1_reraise(rec: Recorder) -> Generator[None, None, None]:
    try:
        yield
    except MyException:
        rec.caught["dep1_reraise"] = True
        raise


def dep2_reraise(rec: Recorder) -> Generator[None, None, None]:
    try:
        yield
    except MyException:
        rec.caught["dep2_reraise"] = True
        raise


async def async_dep1_reraise(rec: Recorder) -> AsyncGenerator[None, None]:
    try:
        yield
    except MyException:
        rec.caught["async_dep1_reraise"] = True
        raise


async def async_dep2_reraise(rec: Recorder) -> AsyncGenerator[None, None]:
    try:
        yield
    except MyException:
        rec.caught["async_dep2_reraise"] = True
        raise


def test_dependency_can_catch_exception_single_sync_reraise() -> None:
    def collector(one: Annotated[None, Marker(dep1_reraise)]) -> None:
        raise MyException

    container = Container()
    rec = Recorder()
    container.bind(bind_by_type(Dependent(lambda: rec), Recorder))
    try:
        with container.enter_scope(None) as state:
            container.execute_sync(
                container.solve(Dependent(collector), scopes=[None]),
                executor=SyncExecutor(),
                state=state,
            )
    except MyException:
        pass
    else:
        raise AssertionError(
            "MyException should have been re-raised"
        )  # pragma: no cover
    assert rec.caught == {"dep1_reraise": True}


@pytest.mark.anyio
async def test_dependency_can_catch_exception_single_async_reraise() -> None:
    def collector(one: Annotated[None, Marker(async_dep1_reraise)]) -> None:
        raise MyException

    container = Container()
    rec = Recorder()
    container.bind(bind_by_type(Dependent(lambda: rec), Recorder))
    try:
        async with container.enter_scope(None) as state:
            await container.execute_async(
                container.solve(Dependent(collector), scopes=[None]),
                executor=AsyncExecutor(),
                state=state,
            )
    except MyException:
        pass
    else:
        raise AssertionError(
            "MyException should have been re-raised"
        )  # pragma: no cover
    assert rec.caught == {"async_dep1_reraise": True}


def test_dependency_can_catch_exception_concurrent_sync_reraise() -> None:
    def collector(
        one: Annotated[None, Marker(dep1_reraise)],
        two: Annotated[None, Marker(dep2_reraise)],
    ) -> None:
        raise MyException

    container = Container()
    rec = Recorder()
    container.bind(bind_by_type(Dependent(lambda: rec), Recorder))
    try:
        with container.enter_scope(None) as state:
            container.execute_sync(
                container.solve(Dependent(collector), scopes=[None]),
                executor=SyncExecutor(),
                state=state,
            )
    except MyException:
        pass
    else:
        raise AssertionError(
            "MyException should have been re-raised"
        )  # pragma: no cover
    assert rec.caught == {"dep1_reraise": True, "dep2_reraise": True}


@pytest.mark.anyio
async def test_dependency_can_catch_exception_concurrent_async_reraise() -> None:
    def collector(
        one: Annotated[None, Marker(async_dep1_reraise)],
        two: Annotated[None, Marker(async_dep2_reraise)],
    ) -> None:
        raise MyException

    container = Container()
    rec = Recorder()
    container.bind(bind_by_type(Dependent(lambda: rec), Recorder))
    try:
        async with container.enter_scope(None) as state:
            await container.execute_async(
                container.solve(Dependent(collector), scopes=[None]),
                executor=AsyncExecutor(),
                state=state,
            )
    except MyException:
        pass
    else:
        raise AssertionError(
            "MyException should have been re-raised"
        )  # pragma: no cover
    assert rec.caught == {"async_dep1_reraise": True, "async_dep2_reraise": True}


@pytest.mark.anyio
async def test_dependency_can_catch_exception_concurrent_mixed_reraise() -> None:
    def collector(
        one: Annotated[None, Marker(async_dep1_reraise)],
        two: Annotated[None, Marker(dep2_reraise)],
    ) -> None:
        raise MyException

    container = Container()
    rec = Recorder()
    container.bind(bind_by_type(Dependent(lambda: rec), Recorder))
    try:
        async with container.enter_scope(None) as state:
            await container.execute_async(
                container.solve(Dependent(collector), scopes=[None]),
                executor=AsyncExecutor(),
                state=state,
            )
    except MyException:
        pass
    else:
        raise AssertionError(
            "MyException should have been re-raised"
        )  # pragma: no cover
    assert rec.caught == {"async_dep1_reraise": True, "dep2_reraise": True}


def test_deep_reraise() -> None:
    def leaf() -> Generator[None, None, None]:
        try:
            yield
        except MyException:
            pass
        else:
            raise AssertionError("Exception did not propagate")  # pragma: no cover

    def parent(child: Annotated[None, Marker(leaf)]) -> Generator[None, None, None]:
        try:
            yield
        except MyException:
            raise

    def root(child: Annotated[None, Marker(parent)]) -> None:
        raise MyException

    container = Container()
    with container.enter_scope(None) as state:
        container.execute_sync(
            container.solve(Dependent(root), scopes=[None]),
            executor=SyncExecutor(),
            state=state,
        )
