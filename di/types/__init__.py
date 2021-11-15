from types import TracebackType
from typing import Generic, Optional, Type, TypeVar, Union

T = TypeVar("T")


class FusedContextManager(Generic[T]):
    __slots__ = ()

    def __enter__(self) -> T:
        ...

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        ...

    async def __aenter__(self) -> T:
        ...

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        ...
