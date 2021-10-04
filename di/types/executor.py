import sys
from typing import Awaitable, Callable, List, TypeVar, Union

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

ResultType = TypeVar("ResultType")

Task = Callable[[], Union[None, Awaitable[None]]]


class SyncExecutor(Protocol):
    def execute_sync(
        self,
        tasks: List[List[Task]],
        get_result: Callable[[], ResultType],
    ) -> ResultType:
        raise NotImplementedError


class AsyncExecutor(Protocol):
    async def execute_async(
        self,
        tasks: List[List[Task]],
        get_result: Callable[[], ResultType],
    ) -> ResultType:
        raise NotImplementedError
