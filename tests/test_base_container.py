import pytest

from di import AsyncExecutor, BaseContainer, Dependant


@pytest.mark.anyio
async def test_base_container_async() -> None:
    async def endpoint() -> int:
        return 123

    dep = Dependant(endpoint)
    executor = AsyncExecutor()
    container = BaseContainer()

    solved = container.solve(dep, scopes=(None,))

    async with container.enter_scope(None) as container:
        res = await container.execute_async(solved, executor=executor)

    assert res == 123
