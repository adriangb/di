"""Black box tests that check the high level API but in practice are written to fully
test all of the execution paths in di/_utils/task.py
"""
import functools
from typing import Any, AsyncGenerator, Callable, Generator

import pytest

from di import Container
from di.dependent import Dependent
from di.executors import ConcurrentAsyncExecutor


def sync_callable_func() -> int:
    return 1


async def async_callable_func() -> int:
    return 1


def sync_gen_func() -> Generator[int, None, None]:
    yield 1


async def async_gen_func() -> AsyncGenerator[int, None]:
    yield 1


class SyncCallableCls:
    def __call__(self) -> int:
        return 1


class AsyncCallableCls:
    async def __call__(self) -> int:
        return 1


class SyncGenCallableCls:
    def __call__(self) -> Generator[int, None, None]:
        yield 1


class AsyncGenCallableCls:
    async def __call__(self) -> AsyncGenerator[int, None]:
        yield 1


def no_wrapper(func: Callable[..., Any]) -> Callable[..., Any]:
    return func


def wrap_in_partial(func: Callable[..., Any]) -> Callable[..., Any]:
    return functools.partial(func)


def wrap_in_wraps(func: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):  # type: ignore
        return func(*args, **kwargs)

    return wrapper  # type: ignore


@pytest.mark.parametrize(
    "dep",
    [
        sync_callable_func,
        async_callable_func,
        sync_gen_func,
        async_gen_func,
        SyncCallableCls(),
        AsyncCallableCls(),
        SyncGenCallableCls(),
        AsyncGenCallableCls(),
    ],
    ids=[
        "sync_callable_func",
        "async_callable_func",
        "sync_gen_func",
        "async_gen_func",
        "SyncCallableCls",
        "AsyncCallableCls",
        "SyncGenCallableCls",
        "AsyncGenCallableCls",
    ],
)
@pytest.mark.parametrize(
    "wrapper",
    [
        no_wrapper,
        wrap_in_partial,
        wrap_in_wraps,
    ],
)
@pytest.mark.parametrize("use_cache", [True, False])
@pytest.mark.anyio
async def test_dependency_types(
    dep: Any,
    wrapper: Callable[[Callable[..., Any]], Callable[..., Any]],
    use_cache: bool,
):
    dep = wrapper(dep)
    container = Container()
    solved = container.solve(Dependent(dep, use_cache=use_cache), scopes=[None])  # type: ignore
    executor = ConcurrentAsyncExecutor()
    async with container.enter_scope(None) as state:
        res = await solved.execute_async(executor=executor, state=state)
        assert res == 1
        # test the cached execution paths
        res = await solved.execute_async(executor=executor, state=state)
        assert res == 1
        # test the by value execution paths
        res = await solved.execute_async(
            executor=executor, values={dep: 2}, state=state
        )
        assert res == 2
