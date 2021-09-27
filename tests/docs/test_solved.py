import pytest

from docs.src import solved_dependant


@pytest.mark.anyio
async def test_solved() -> None:
    await solved_dependant.framework()
