import os
import sys
import tempfile
from platform import python_implementation
from unittest.mock import patch

import anyio
import pytest


@pytest.mark.skipif(os.name == "nt", reason="Textual doesn't support Windows")
@pytest.mark.skipif(
    python_implementation().lower() != "cpython", reason="Textual only runs on CPython"
)
@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_textual():
    from docs.src.textual.demo import GridTest  # type: ignore[import]

    with tempfile.NamedTemporaryFile(mode="w+") as stdin:
        with patch.object(sys, "stdin", stdin):
            # enough time for the app to fail
            async with anyio.move_on_after(1):
                await GridTest().process_messages()
