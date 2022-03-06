import anyio
import anyio.abc

from di.api.executor import AsyncExecutorProtocol, State, Task, TaskGraph
from di.executors._concurrency import callable_in_thread_pool


class AsyncExecutor(AsyncExecutorProtocol):
    async def execute_async(self, tasks: TaskGraph, state: State) -> None:
        for task in tasks.static_order():
            maybe_aw = task.compute(state)
            if maybe_aw is not None:
                await maybe_aw


async def _async_worker(
    task: Task,
    tasks: TaskGraph,
    state: State,
    taskgroup: anyio.abc.TaskGroup,
) -> None:
    if getattr(task.dependant, "sync_to_thread", False):
        await callable_in_thread_pool(task.compute)(state)
    else:
        maybe_aw = task.compute(state)
        if maybe_aw is not None:
            await maybe_aw
    tasks.done(task)
    for task in tasks.get_ready():
        taskgroup.start_soon(_async_worker, task, tasks, state, taskgroup)


class ConcurrentAsyncExecutor(AsyncExecutorProtocol):
    async def execute_async(self, tasks: TaskGraph, state: State) -> None:
        async with anyio.create_task_group() as taskgroup:
            for task in tasks.get_ready():
                taskgroup.start_soon(_async_worker, task, tasks, state, taskgroup)
