import contextvars
from typing import Any, Awaitable, Callable, TypeVar

try:
    import anyio
except ImportError as e:
    raise ImportError(
        "Using AsyncExector or ConcurrentAsyncExecutor requires installing anyio"
        " (`pip install anyio`) or the anyio extra (`pip install di[anyio]`)"
    ) from e
import anyio.abc

from di.api.executor import StateType, SupportsAsyncExecutor, SupportsTaskGraph, Task

T = TypeVar("T")


def callable_in_thread_pool(call: Callable[..., T]) -> Callable[..., Awaitable[T]]:
    def inner(*args: Any, **kwargs: Any) -> "Awaitable[T]":
        return anyio.to_thread.run_sync(
            contextvars.copy_context().run, lambda: call(*args, **kwargs)
        )  # type: ignore[return-value]

    return inner


async def _execute_task(task: Task[StateType], state: StateType) -> None:
    if getattr(task.dependant, "sync_to_thread", False):
        await callable_in_thread_pool(task.compute)(state)
    else:
        maybe_aw = task.compute(state)
        if maybe_aw is not None:
            await maybe_aw


class AsyncExecutor(SupportsAsyncExecutor):
    async def execute_async(
        self, tasks: SupportsTaskGraph[StateType], state: StateType
    ) -> None:
        for task in tasks.static_order():
            await _execute_task(task, state)


async def async_worker(
    task: Task[StateType],
    tasks: SupportsTaskGraph[StateType],
    state: StateType,
    taskgroup: anyio.abc.TaskGroup,
) -> None:
    await _execute_task(task, state)
    tasks.done(task)
    for task in tasks.get_ready():
        taskgroup.start_soon(async_worker, task, tasks, state, taskgroup)


class ConcurrentAsyncExecutor(SupportsAsyncExecutor):
    async def execute_async(
        self, tasks: SupportsTaskGraph[StateType], state: StateType
    ) -> None:
        async with anyio.create_task_group() as taskgroup:
            for task in tasks.get_ready():
                taskgroup.start_soon(async_worker, task, tasks, state, taskgroup)
