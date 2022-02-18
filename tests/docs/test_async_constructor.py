import pytest

from docs_src.async_constructor import main


@pytest.mark.anyio("asyncio")
async def test_async_constructor() -> None:
    await main()
