from di.api.executor import StateType, SupportsSyncExecutor, SupportsTaskGraph


class SyncExecutor(SupportsSyncExecutor):
    def execute_sync(
        self, tasks: SupportsTaskGraph[StateType], state: StateType
    ) -> None:
        for task in tasks.static_order():
            maybe_aw = task.compute(state)
            if maybe_aw is not None:
                raise TypeError("Cannot execute async dependencies in execute_sync")
