import sys
from types import TracebackType
from typing import Optional, Type, TypeVar, Union

if sys.version_info >= (3, 8):
    from typing import Protocol
else:
    from typing_extensions import Protocol

T = TypeVar("T", covariant=True)


class FusedContextManager(Protocol[T]):
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
