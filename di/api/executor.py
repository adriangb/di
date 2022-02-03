from __future__ import annotations

import sys
from typing import Any, Awaitable, Iterable, Optional, Union

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

from di.api.dependencies import DependantBase


class State:
    __slots__ = ()


class Task(Protocol):
    dependant: DependantBase[Any]
    is_async: bool

    def compute(
        self, state: State
    ) -> Union[Iterable[Union[None, Task]], Awaitable[Iterable[Union[None, Task]]]]:
        ...


class SyncExecutorProtocol(Protocol):
    def execute_sync(self, tasks: Iterable[Optional[Task]], state: State) -> None:
        raise NotImplementedError


class AsyncExecutorProtocol(Protocol):
    async def execute_async(
        self, tasks: Iterable[Optional[Task]], state: State
    ) -> None:
        raise NotImplementedError
