import pytest

from di.exceptions import ScopeViolationError
from docs_src import invalid_scope_dependance


def test_invalid_scope_dependance() -> None:
    with pytest.raises(ScopeViolationError):
        invalid_scope_dependance.framework()
