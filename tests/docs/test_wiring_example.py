import pytest

from di.exceptions import ScopeViolationError
from docs.src import invalid_scope_dependance


@pytest.mark.anyio
async def test_invalid_scope_dependance() -> None:
    with pytest.raises(ScopeViolationError):
        await invalid_scope_dependance.framework()
