import pytest

from docs.src import bind_as_a_dep


@pytest.mark.anyio
async def test_bind_as_a_dep() -> None:
    await bind_as_a_dep.framework()
