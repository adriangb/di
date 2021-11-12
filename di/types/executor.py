from __future__ import annotations

import sys
import typing
from typing import Any, Awaitable, Iterable, Union

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

from di.types.dependencies import DependantBase


class TaskInfo(typing.NamedTuple):
    dependant: DependantBase[Any]
    task: Task


AsyncTaskReturnValue = Awaitable[Iterable[Union[None, TaskInfo]]]
SyncTaskReturnValue = Iterable[Union[None, TaskInfo]]


class Task(Protocol):
    def __call__(self) -> Union[AsyncTaskReturnValue, SyncTaskReturnValue]:
        ...


class SyncExecutor(Protocol):
    def execute_sync(self, tasks: Iterable[Task]) -> None:
        raise NotImplementedError


class AsyncExecutor(Protocol):
    async def execute_async(self, tasks: Iterable[Task]) -> None:
        raise NotImplementedError
