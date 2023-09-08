import pytest

from di.exceptions import ScopeViolationError
from docs_src import default_scope, invalid_scope_dependence


def test_invalid_scope_dependence() -> None:
    with pytest.raises(ScopeViolationError):
        invalid_scope_dependence.framework()


@pytest.mark.anyio
async def test_default_scopes() -> None:
    await default_scope.web_framework()
