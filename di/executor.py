import typing

ResultType = typing.TypeVar("ResultType")

Task = typing.Union[
    typing.Callable[[], None], typing.Callable[[], typing.Awaitable[None]]
]


class Executor(typing.Protocol):
    def execute(
        self,
        tasks: typing.List[typing.Set[Task]],
        get_result: typing.Callable[[], ResultType],
    ) -> typing.Union[ResultType, typing.Awaitable[ResultType]]:
        ...
