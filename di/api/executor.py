from __future__ import annotations

import sys
from typing import Any, Awaitable, Callable, Hashable, Iterable, Union

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

from di.api.dependencies import DependantBase


class State:
    __slots__ = ()


class Task(Hashable, Protocol):
    dependant: DependantBase[Any]
    compute: Union[Callable[[State], None], Callable[[State], Awaitable[None]]]


class TaskGraph(Protocol):
    def done(self, task: Task) -> None:
        ...

    def get_ready(self) -> Iterable[Task]:
        ...

    def is_active(self) -> bool:
        ...

    def static_order(self) -> Iterable[Task]:
        ...


class SyncExecutorProtocol(Protocol):
    def execute_sync(self, tasks: TaskGraph, state: State) -> None:
        raise NotImplementedError


class AsyncExecutorProtocol(Protocol):
    async def execute_async(self, tasks: TaskGraph, state: State) -> None:
        raise NotImplementedError
