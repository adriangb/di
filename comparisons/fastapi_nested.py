import asyncio
from contextlib import AsyncExitStack
from time import time

from fastapi import Depends, Request  # noqa
from fastapi.dependencies.utils import get_dependant, solve_dependencies

tempalate = "async def func_{}({}): return 1"

for f in range(15):
    params = []
    for p in range(f):
        params.append(f"v{p}: int = Depends(func_{p})")
    param_code = ", ".join(params)
    code = tempalate.format(f, param_code)
    exec(code)

final = eval(f"func_{f}")


async def test(request: Request):
    res = await solve_dependencies(request=request, dependant=get_dependant(path="/", call=final))
    values, *_, cache = res
    r = await final(**values)
    assert r == 1


async def main():
    t = []
    for _ in range(10):  # 10 incoming requests
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
