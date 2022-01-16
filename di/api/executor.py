from __future__ import annotations

import sys
from typing import Any, Iterable, NewType, Optional, Union

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

from di.api.dependencies import DependantBase

State = NewType("State", object)


class AsyncTask:
    __slots__ = ()
    dependant: DependantBase[Any]

    async def compute(self, state: State) -> Iterable[Union[None, Task]]:
        ...


class SyncTask:
    __slots__ = ()
    dependant: DependantBase[Any]

    def compute(self, state: State) -> Iterable[Union[None, Task]]:
        ...


Task = Union[AsyncTask, SyncTask]


class SyncExecutorProtocol(Protocol):
    def execute_sync(self, tasks: Iterable[Optional[Task]], state: State) -> None:
        raise NotImplementedError


class AsyncExecutorProtocol(Protocol):
    async def execute_async(
        self, tasks: Iterable[Optional[Task]], state: State
    ) -> None:
        raise NotImplementedError
