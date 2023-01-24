try:
    import anyio
except ImportError as e:
    raise ImportError(
        "Using AsyncExector or ConcurrentAsyncExecutor requires installing anyio"
        " (`pip install anyio`) or the anyio extra (`pip install di[anyio]`)"
    ) from e
import anyio.abc

from di.api.executor import (
    ExecutionState,
    SupportsAsyncExecutor,
    SupportsTaskGraph,
    Task,
)


class AsyncExecutor(SupportsAsyncExecutor):
    """An executor that executes sync and async dependencies sequentially."""

    async def execute_async(
        self, tasks: SupportsTaskGraph, state: ExecutionState
    ) -> None:
        for task in tasks.static_order():
            maybe_aw = task.compute(state)
            if maybe_aw is not None:
                await maybe_aw


async def async_worker(
    task: Task,
    tasks: SupportsTaskGraph,
    state: ExecutionState,
    taskgroup: anyio.abc.TaskGroup,
) -> None:
    maybe_aw = task.compute(state)
    if maybe_aw is not None:
        await maybe_aw
    tasks.done(task)
    for task in tasks.get_ready():
        taskgroup.start_soon(async_worker, task, tasks, state, taskgroup)


class ConcurrentAsyncExecutor(SupportsAsyncExecutor):
    async def execute_async(
        self, tasks: SupportsTaskGraph, state: ExecutionState
    ) -> None:
        async with anyio.create_task_group() as taskgroup:
            for task in tasks.get_ready():
                taskgroup.start_soon(async_worker, task, tasks, state, taskgroup)
