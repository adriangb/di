import pytest

from docs_src import web_framework


@pytest.mark.anyio
async def test_web_framework_example() -> None:
    web_framework.main()
