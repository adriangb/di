from typing import TypeVar

from di.types import FusedContextManager

T = TypeVar("T")


class nullcontext(FusedContextManager[T]):
    """Backport of contextlib.nullcontext"""

    def __init__(self, enter_result: T) -> None:
        self.enter_result = enter_result

    def __enter__(self) -> T:
        return self.enter_result

    def __exit__(self, *excinfo):  # type: ignore
        pass

    async def __aenter__(self) -> T:
        return self.enter_result

    async def __aexit__(self, *excinfo) -> T:  # type: ignore
        pass
