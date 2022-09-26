from contextlib import AsyncExitStack, asynccontextmanager
from contextvars import ContextVar
from typing import Generator

import pytest

from di.concurrency import as_async

ctx: ContextVar[str] = ContextVar("ctx")


@as_async
def callable(val: int) -> int:
    return val


@as_async
def context_manager_like(val: int) -> Generator[int, None, None]:
    yield val


class MyException(Exception):
    pass


@as_async
def context_manager_exc_startup(val: int) -> Generator[int, None, None]:
    raise MyException
    yield val  # type: ignore


@as_async
def context_manager_exc_teardown(val: int) -> Generator[int, None, None]:
    yield val  # type: ignore
    raise MyException


@as_async
def context_manager_catch_exc(val: int) -> Generator[int, None, None]:
    try:
        yield val  # type: ignore
    except MyException:
        pass
    else:
        raise AssertionError("MyException was not raised")


@pytest.mark.anyio
async def test_as_async_cm() -> None:
    wrapped_cm = asynccontextmanager(context_manager_like)
    async with wrapped_cm(2) as res:
        assert res == 2


@pytest.mark.anyio
async def test_as_async_call() -> None:
    res = await callable(1)
    assert res == 1


@pytest.mark.anyio
async def test_as_async_cm_raises_exc_in_startup() -> None:
    wrapped_cm = asynccontextmanager(context_manager_exc_startup)
    with pytest.raises(MyException):
        async with wrapped_cm(123):
            assert False, "Should not be called"


@pytest.mark.anyio
async def test_as_async_cm_raises_exc_in_teardown() -> None:
    wrapped_cm = asynccontextmanager(context_manager_exc_teardown)
    async with AsyncExitStack() as stack:
        res = await stack.enter_async_context(wrapped_cm(4))
        assert res == 4
        with pytest.raises(MyException):
            await stack.aclose()


@pytest.mark.anyio
async def test_as_async_cm_catches_exception() -> None:
    wrapped_cm = asynccontextmanager(context_manager_catch_exc)
    async with wrapped_cm(5) as res:
        assert res == 5
        raise MyException
