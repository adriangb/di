from __future__ import annotations

import sys
from typing import Hashable, Iterable, Optional, Union

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol


class AsyncTask(Hashable, Protocol):
    async def __call__(self) -> Iterable[Optional[Union[SyncTask, AsyncTask]]]:
        ...


class SyncTask(Hashable, Protocol):
    def __call__(self) -> Iterable[Optional[Union[SyncTask, AsyncTask]]]:
        ...


Task = Union[AsyncTask, SyncTask]


class SyncExecutor(Protocol):
    def execute_sync(self, tasks: Iterable[Task]) -> None:
        raise NotImplementedError


class AsyncExecutor(Protocol):
    async def execute_async(self, tasks: Iterable[Task]) -> None:
        raise NotImplementedError
