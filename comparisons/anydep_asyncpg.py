import asyncio
from time import time
from typing import AsyncGenerator

import asyncpg

from anydep.container import Container
from anydep.params import Depends


async def db_conn_pool() -> AsyncGenerator[asyncpg.Connection, None]:
    async with asyncpg.create_pool(user="postgres", password="mysecretpassword") as pool:
        yield pool


async def db_conn(pool: asyncpg.Pool = Depends(db_conn_pool, scope="app")) -> AsyncGenerator[asyncpg.Connection, None]:
    async with pool.acquire() as conn:
        yield conn


async def endpoint(conn: asyncpg.Connection = Depends(db_conn)) -> int:
    return await conn.fetchval("select 2 ^ 8")


async def test(container: Container):
    r = await container.execute(container.get_dependant(endpoint))
    assert r == 256


async def main():
    container = Container()
    t = []
    async with container.enter_global_scope("app"):
        for _ in range(100):  # 100 incoming requests
            async with container.enter_local_scope("request"):
                start = time()
                await test(container)
            t.append(time() - start)
    average = sum(t) / len(t)
    worst = max(t)
    worst_idx = t.index(worst)
    print(f"Average: {average:0.5f}\nWorst: {worst:0.5f}@{worst_idx}")


asyncio.run(main())
