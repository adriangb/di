from di.api.executor import ExecutionState, SupportsSyncExecutor, SupportsTaskGraph


class SyncExecutor(SupportsSyncExecutor):
    """An executor that executes only sync dependencies.

    Dependencies are executed sequentially.
    If any async dependencies are encountered a RuntimeError will be raised.
    If there are no async dependencies, this will be faster than using `AsyncExecutor` because there is no event loop overhead.
    """

    def execute_sync(self, tasks: SupportsTaskGraph, state: ExecutionState) -> None:
        for task in tasks.static_order():
            maybe_aw = task.compute(state)
            if maybe_aw is not None:
                raise TypeError("Cannot execute async dependencies in execute_sync")
