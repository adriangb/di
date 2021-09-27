import pytest

from docs.src import sharing


@pytest.mark.anyio
async def test_web_framework_example() -> None:
    await sharing.main()
