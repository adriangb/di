import pytest

from di.exceptions import ScopeViolationError
from docs_src import inferred_scopes, invalid_scope_dependance


def test_invalid_scope_dependance() -> None:
    with pytest.raises(ScopeViolationError):
        invalid_scope_dependance.framework()


@pytest.mark.anyio
async def test_inferred_scopes() -> None:
    await inferred_scopes.web_framework()
