import typing

ResultType = typing.TypeVar("ResultType")

Task = typing.Union[
    typing.Callable[[], None], typing.Callable[[], typing.Awaitable[None]]
]


class SyncExecutor(typing.Protocol):
    def execute_sync(
        self,
        tasks: typing.List[typing.List[Task]],
        get_result: typing.Callable[[], ResultType],
    ) -> ResultType:
        raise NotImplementedError


class AsyncExecutor(typing.Protocol):
    async def execute_async(
        self,
        tasks: typing.List[typing.List[Task]],
        get_result: typing.Callable[[], ResultType],
    ) -> ResultType:
        raise NotImplementedError
