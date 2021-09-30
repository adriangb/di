from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, Generator

import pytest

from di import Container, Dependant, Depends


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
    def collector(one: None = Depends(dep1)) -> None:
        raise MyException

    container = Container()
    rec = Recorder()
    container.bind(Dependant(lambda: rec), Recorder)
    container.execute_sync(container.solve(Dependant(collector)))
    assert rec.caught == {"dep1": True}


@pytest.mark.anyio
async def test_dependency_can_catch_exception_single_async() -> None:
    def collector(one: None = Depends(async_dep1)) -> None:
        raise MyException

    container = Container()
    rec = Recorder()
    container.bind(Dependant(lambda: rec), Recorder)
    await container.execute_async(container.solve(Dependant(collector)))
    assert rec.caught == {"async_dep1": True}


def test_dependency_can_catch_exception_concurrent_sync() -> None:
    def collector(one: None = Depends(dep1), two: None = Depends(dep2)) -> None:
        raise MyException

    container = Container()
    rec = Recorder()
    container.bind(Dependant(lambda: rec), Recorder)
    container.execute_sync(container.solve(Dependant(collector)))
    # one of the dependencies catches and swallows the exception
    # so the other one nevers sees it
    # there is no promises as to the order, both cases are valid
    assert rec.caught == {"dep1": True} or rec.caught == {"dep2": True}


@pytest.mark.anyio
async def test_dependency_can_catch_exception_concurrent_async() -> None:
    def collector(
        one: None = Depends(async_dep1), two: None = Depends(async_dep2)
    ) -> None:
        raise MyException

    container = Container()
    rec = Recorder()
    container.bind(Dependant(lambda: rec), Recorder)
    await container.execute_async(container.solve(Dependant(collector)))
    # one of the dependencies catches and swallows the exception
    # so the other one nevers sees it
    # there is no promises as to the order, both cases are valid
    assert rec.caught == {"async_dep1": True} or rec.caught == {"async_dep2": True}


@pytest.mark.anyio
async def test_dependency_can_catch_exception_concurrent_mixed() -> None:
    def collector(one: None = Depends(async_dep1), two: None = Depends(dep2)) -> None:
        raise MyException

    container = Container()
    rec = Recorder()
    container.bind(Dependant(lambda: rec), Recorder)
    await container.execute_async(container.solve(Dependant(collector)))
    # one of the dependencies catches and swallows the exception
    # so the other one nevers sees it
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
    def collector(one: None = Depends(dep1_reraise)) -> None:
        raise MyException

    container = Container()
    rec = Recorder()
    container.bind(Dependant(lambda: rec), Recorder)
    try:
        container.execute_sync(container.solve(Dependant(collector)))
    except MyException:
        pass
    else:
        raise AssertionError("MyException should have been re-raised")
    assert rec.caught == {"dep1_reraise": True}


@pytest.mark.anyio
async def test_dependency_can_catch_exception_single_async_reraise() -> None:
    def collector(one: None = Depends(async_dep1_reraise)) -> None:
        raise MyException

    container = Container()
    rec = Recorder()
    container.bind(Dependant(lambda: rec), Recorder)
    try:
        await container.execute_async(container.solve(Dependant(collector)))
    except MyException:
        pass
    else:
        raise AssertionError("MyException should have been re-raised")
    assert rec.caught == {"async_dep1_reraise": True}


def test_dependency_can_catch_exception_concurrent_sync_reraise() -> None:
    def collector(
        one: None = Depends(dep1_reraise), two: None = Depends(dep2_reraise)
    ) -> None:
        raise MyException

    container = Container()
    rec = Recorder()
    container.bind(Dependant(lambda: rec), Recorder)
    try:
        container.execute_sync(container.solve(Dependant(collector)))
    except MyException:
        pass
    else:
        raise AssertionError("MyException should have been re-raised")
    assert rec.caught == {"dep1_reraise": True, "dep2_reraise": True}


@pytest.mark.anyio
async def test_dependency_can_catch_exception_concurrent_async_reraise() -> None:
    def collector(
        one: None = Depends(async_dep1_reraise), two: None = Depends(async_dep2_reraise)
    ) -> None:
        raise MyException

    container = Container()
    rec = Recorder()
    container.bind(Dependant(lambda: rec), Recorder)
    try:
        await container.execute_async(container.solve(Dependant(collector)))
    except MyException:
        pass
    else:
        raise AssertionError("MyException should have been re-raised")
    assert rec.caught == {"async_dep1_reraise": True, "async_dep2_reraise": True}


@pytest.mark.anyio
async def test_dependency_can_catch_exception_concurrent_mixed_reraise() -> None:
    def collector(
        one: None = Depends(async_dep1_reraise), two: None = Depends(dep2_reraise)
    ) -> None:
        raise MyException

    container = Container()
    rec = Recorder()
    container.bind(Dependant(lambda: rec), Recorder)
    try:
        await container.execute_async(container.solve(Dependant(collector)))
    except MyException:
        pass
    else:
        raise AssertionError("MyException should have been re-raised")
    assert rec.caught == {"async_dep1_reraise": True, "dep2_reraise": True}


def test_deep_reraise() -> None:
    def leaf() -> Generator[None, None, None]:
        try:
            yield
        except MyException:
            pass
        else:
            raise AssertionError("Exception did not propagate")

    def parent(child: None = Depends(leaf)) -> Generator[None, None, None]:
        try:
            yield
        except MyException:
            raise

    def root(child: None = Depends(parent)) -> None:
        raise MyException

    container = Container()
    container.execute_sync(container.solve(Dependant(root)))
