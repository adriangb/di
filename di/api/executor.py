from __future__ import annotations

import sys
import typing
from typing import Any, Iterable, Union

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

from di.api.dependencies import DependantBase


class AsyncTaskInfo(typing.NamedTuple):
    dependant: DependantBase[Any]
    task: AsyncTask


class SyncTaskInfo(typing.NamedTuple):
    dependant: DependantBase[Any]
    task: SyncTask


TaskInfo = Union[AsyncTaskInfo, SyncTaskInfo]


class AsyncTask(Protocol):
    async def __call__(self) -> Iterable[Union[None, TaskInfo]]:
        ...


class SyncTask(Protocol):
    def __call__(self) -> Iterable[Union[None, TaskInfo]]:
        ...


class SyncExecutor(Protocol):
    def execute_sync(self, tasks: Iterable[TaskInfo]) -> None:
        raise NotImplementedError


class AsyncExecutor(Protocol):
    async def execute_async(self, tasks: Iterable[TaskInfo]) -> None:
        raise NotImplementedError
