import threading
from contextlib import contextmanager
from typing import Iterator

import anyio
import pytest

from di._utils.concurrency import contextmanager_in_threadpool


@contextmanager
def must_be_same_thread() -> Iterator[None]:
    thread = threading.get_ident()
    try:
        yield
    finally:
        assert threading.get_ident() == thread


@pytest.mark.anyio
async def test_same_thread() -> None:
    async def run() -> None:
        # stagger entering the context managers
        await anyio.sleep(0.01)
        async with contextmanager_in_threadpool(must_be_same_thread()):
            # delay here to give someone else a chance to steal our thread
            await anyio.sleep(0.01)

    # run a lot of copies concurrently to ensure we saturate the thread pool
    async with anyio.create_task_group() as tg:
        for _ in range(1_000):
            tg.start_soon(run)
