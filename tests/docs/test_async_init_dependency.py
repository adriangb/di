import pytest

from docs_src.async_init_dependency import main


@pytest.mark.anyio("asyncio")
async def test_async_init_dependency() -> None:
    await main()
