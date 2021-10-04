import sys

import pytest

from docs.src import gather_deps_example


@pytest.mark.anyio
@pytest.mark.skipif(sys.version_info < (3, 7), reason="Can't runtime check protocol")
async def test_web_framework_example() -> None:
    await gather_deps_example.web_framework()
