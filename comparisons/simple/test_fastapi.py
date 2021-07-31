from contextlib import AsyncExitStack
from time import time

import anyio
from fastapi import Depends, Request
from fastapi.dependencies.utils import get_dependant, solve_dependencies


async def coroutine1():
    await anyio.sleep(1)
    return 1


async def coroutine2():
    await anyio.sleep(1)
    return 2


async def collector(v1: int = Depends(coroutine1), v2: int = Depends(coroutine2)):
    return v1 + v2


async def test(request: Request):
    res = await solve_dependencies(request=request, dependant=get_dependant(path="/", call=collector))
    values, *_, cache = res
    await collector(**values)


async def main():
    start = time()
    async with AsyncExitStack() as stack:
        request = Request(scope={"type": "http", "fastapi_astack": stack, "query_string": None, "headers": {}})
        await test(request=request)
    print(time() - start)


if __name__ == "__main__":
    anyio.run(main)
