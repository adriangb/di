import sys

import pytest

from docs.src import sharing


@pytest.mark.skipif(
    sys.version_info < (3, 8), reason="Missing type annotations in stdlib"
)
def test_web_framework_example() -> None:
    sharing.main()
