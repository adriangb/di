import pytest

from docs.src import web_framework


@pytest.mark.anyio
async def test_web_framework_example() -> None:
    await web_framework.web_framework()
