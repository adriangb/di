from __future__ import annotations

import sys
from typing import Awaitable, Iterable, Optional, Union

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol


class Task(Protocol):
    def __call__(
        self,
    ) -> Union[Awaitable[Iterable[Optional[Task]]], Iterable[Optional[Task]]]:
        ...


class SyncExecutor(Protocol):
    def execute_sync(self, tasks: Iterable[Task]) -> None:
        raise NotImplementedError


class AsyncExecutor(Protocol):
    async def execute_async(self, tasks: Iterable[Task]) -> None:
        raise NotImplementedError
