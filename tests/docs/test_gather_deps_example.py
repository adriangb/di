import pytest

from docs.src import gather_deps_example


@pytest.mark.anyio
async def test_web_framework_example() -> None:
    await gather_deps_example.web_framework()
