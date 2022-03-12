from __future__ import annotations

import sys
from typing import Awaitable, Callable, Hashable, Iterable, TypeVar, Union

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

from di.api.dependencies import DependantBase

StateType = TypeVar("StateType")


class Task(Hashable, Protocol[StateType]):
    dependant: DependantBase[StateType]

    @property
    def compute(self) -> Callable[[StateType], Union[Awaitable[None], None]]:
        ...


class SupportsTaskGraph(Protocol[StateType]):
    def done(self, task: Task[StateType]) -> None:
        ...

    def get_ready(self) -> Iterable[Task[StateType]]:
        ...

    def is_active(self) -> bool:
        ...

    def static_order(self) -> Iterable[Task[StateType]]:
        ...


class SupportsSyncExecutor(Protocol):
    def execute_sync(
        self, tasks: SupportsTaskGraph[StateType], state: StateType
    ) -> None:
        raise NotImplementedError


class SupportsAsyncExecutor(Protocol):
    async def execute_async(
        self, tasks: SupportsTaskGraph[StateType], state: StateType
    ) -> None:
        raise NotImplementedError
