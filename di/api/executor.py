from __future__ import annotations

import sys
from typing import Any, Awaitable, Callable, Hashable, Iterable, Union

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

from di._task import ExecutionState
from di.api.dependencies import DependentBase


class Task(Hashable, Protocol):
    dependent: DependentBase[Any]

    @property
    def compute(self) -> Callable[[ExecutionState], Union[Awaitable[None], None]]:
        ...


class SupportsTaskGraph(Protocol):
    def done(self, task: Task) -> None:
        ...

    def get_ready(self) -> Iterable[Task]:
        ...

    def is_active(self) -> bool:
        ...

    def static_order(self) -> Iterable[Task]:
        ...


class SupportsSyncExecutor(Protocol):
    def execute_sync(self, tasks: SupportsTaskGraph, state: ExecutionState) -> None:
        raise NotImplementedError


class SupportsAsyncExecutor(Protocol):
    async def execute_async(
        self, tasks: SupportsTaskGraph, state: ExecutionState
    ) -> None:
        raise NotImplementedError
