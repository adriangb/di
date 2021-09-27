import pytest

from docs.src import headers_example


@pytest.mark.anyio
async def test_web_framework_example() -> None:
    await headers_example.web_framework()
