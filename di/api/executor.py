from __future__ import annotations

import sys
from typing import Any, Awaitable, Iterable, Optional, Union

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

from di.api.dependencies import DependantBase


class Task(Protocol):
    dependant: DependantBase[Any]
    is_async: bool

    def compute(
        self, state: Any
    ) -> Union[Iterable[Union[None, Task]], Awaitable[Iterable[Union[None, Task]]]]:
        ...


class SyncExecutorProtocol(Protocol):
    def execute_sync(self, tasks: Iterable[Optional[Task]], state: Any) -> None:
        raise NotImplementedError


class AsyncExecutorProtocol(Protocol):
    async def execute_async(self, tasks: Iterable[Optional[Task]], state: Any) -> None:
        raise NotImplementedError
