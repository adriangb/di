from typing import TypeVar

from di._utils.types import FusedContextManager

T = TypeVar("T")


class nullcontext(FusedContextManager[T]):
    """Backport of contextlib.nullcontext"""

    __slots__ = ("return_value",)

    def __init__(self, return_value: T) -> None:
        self.return_value = return_value

    def __enter__(self) -> T:
        return self.return_value

    def __exit__(self, *excinfo) -> bool:  # type: ignore
        return False

    async def __aenter__(self) -> T:
        return self.return_value

    async def __aexit__(self, *excinfo) -> bool:  # type: ignore
        return False
