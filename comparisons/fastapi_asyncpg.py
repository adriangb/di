import asyncio
from contextlib import AsyncExitStack
from time import time
from typing import AsyncGenerator

import asyncpg
from fastapi import Depends, Request
from fastapi.dependencies.utils import get_dependant, solve_dependencies


async def db_conn_pool() -> AsyncGenerator[asyncpg.Connection, None]:
    async with asyncpg.create_pool(user="postgres", password="mysecretpassword") as pool:
        yield pool


async def db_conn(pool: asyncpg.Pool = Depends(db_conn_pool)) -> AsyncGenerator[asyncpg.Connection, None]:
    async with pool.acquire() as conn:
        yield conn


async def endpoint(conn: asyncpg.Connection = Depends(db_conn)) -> int:
    return await conn.fetchval("select 2 ^ 8")


async def test(request: Request):
    res = await solve_dependencies(request=request, dependant=get_dependant(path="/", call=endpoint))
    values, *_, cache = res
    r = await endpoint(**values)
    assert r == 256


async def main():
    t = []
    for _ in range(100):  # 100 incoming requests
        async with AsyncExitStack() as stack:
            request = Request(scope={"type": "http", "fastapi_astack": stack, "query_string": None, "headers": {}})
            start = time()
            await test(request=request)
        t.append(time() - start)
    average = sum(t) / len(t)
    worst = max(t)
    worst_idx = t.index(worst)
    print(f"Average: {average:0.5f}\nWorst: {worst:0.5f}@{worst_idx}")


asyncio.run(main())
