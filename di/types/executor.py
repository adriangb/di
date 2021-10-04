from typing import Awaitable, Callable, List, TypeVar, Union

try:
    from typing import Protocol
except ImportError:
    from typing_extensions import Protocol  # type: ignore

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
