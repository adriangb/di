from typing import Awaitable, Callable, List

import pytest

from di.executors import DefaultExecutor
from di.types.executor import Values


async def task(values: Values) -> None:
    ...


@pytest.mark.anyio
@pytest.mark.parametrize("tasks", [[[task]], [[task, task]]])
async def test_async_dep_execute_sync(tasks: List[List[Callable[[], Awaitable[None]]]]):
    exc = DefaultExecutor()
    with pytest.raises(
        TypeError, match="Cannot execute async dependencies in execute_sync"
    ):
        exc.execute_sync(tasks, lambda: None, {})  # type: ignore
