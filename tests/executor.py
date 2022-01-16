from di import AsyncExecutor, SyncExecutor


class TestExecutor(SyncExecutor, AsyncExecutor):
    pass  # pragma: no cover


test_executor = TestExecutor()
