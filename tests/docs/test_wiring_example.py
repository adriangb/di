import pytest

from docs.src import autowiring, manual_wiring


@pytest.mark.anyio
async def test_autowiring_example() -> None:
    await autowiring.framework()


@pytest.mark.anyio
async def test_manual_wiring_example() -> None:
    await manual_wiring.framework()
