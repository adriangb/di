import sys
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Generic, Optional, Type, TypeVar, Union

if sys.version_info < (3, 8):  # pragma: no cover
    from typing_extensions import Protocol
else:  # pragma: no cover
    from typing import Protocol


T = TypeVar("T")


class CacheKey(Protocol):
    def __hash__(self) -> int:
        ...

    def __eq__(self, __o: object) -> bool:
        ...


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


@dataclass
class Some:
    value: Any
