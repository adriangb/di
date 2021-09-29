import pytest

from docs.src import wiring


@pytest.mark.anyio
async def test_invalid_scope_dependance() -> None:
    await wiring.framework()
