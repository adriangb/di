from di.types import FusedContextManager


class nullcontext(FusedContextManager[None]):
    """Backport of contextlib.nullcontext"""

    def __enter__(self) -> None:
        return None

    def __exit__(self, *excinfo) -> bool:  # type: ignore
        return False

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *excinfo) -> bool:  # type: ignore
        return False
