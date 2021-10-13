import sys
from typing import Any, Awaitable, Callable, List, Mapping, TypeVar, Union

from di.types.providers import DependencyProvider

if sys.version_info < (3, 8):
    from typing_extensions import Protocol
else:
    from typing import Protocol

ResultType = TypeVar("ResultType")
Dependency = Any

Values = Mapping[DependencyProvider, Dependency]

Task = Callable[[Values], Union[None, Awaitable[None]]]


class SyncExecutor(Protocol):
    def execute_sync(
        self,
        tasks: List[List[Task]],
        get_result: Callable[[], ResultType],
        values: Values,
    ) -> ResultType:
        raise NotImplementedError


class AsyncExecutor(Protocol):
    async def execute_async(
        self,
        tasks: List[List[Task]],
        get_result: Callable[[], ResultType],
        values: Values,
    ) -> ResultType:
        raise NotImplementedError
