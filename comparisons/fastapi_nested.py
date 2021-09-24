import asyncio
from contextlib import AsyncExitStack
from time import time

from fastapi import Depends, Request  # noqa
from fastapi.dependencies.utils import get_dependant, solve_dependencies

counter = {"counter": 0}

tempalate = "async def func_{}({}): counter['counter'] += 1;return 1"

NESTING = 15
ITER = 3

for f in range(NESTING):
    params = []
    for p in range(f):
        params.append(f"v{p}: int = Depends(func_{p})")
    param_code = ", ".join(params)
    code = tempalate.format(f, param_code)
    exec(code)

final = eval(f"func_{f}")


async def test(request: Request):
    res = await solve_dependencies(
        request=request, dependant=get_dependant(path="/", call=final)
    )
    values, *_, cache = res
    r = await final(**values)
    assert r == 1


async def main():
    t = []
    counter["counter"] = 0
    for _ in range(ITER):  # 10 incoming requests
        async with AsyncExitStack() as stack:
            request = Request(
                scope={
                    "type": "http",
                    "fastapi_astack": stack,
                    "query_string": None,
                    "headers": {},
                }
            )
            start = time()
            await test(request=request)
        t.append(time() - start)
    assert counter["counter"] == NESTING * ITER
    average = sum(t) / len(t)
    worst = max(t)
    worst_idx = t.index(worst)
    print(f"Average: {average:0.5f}\nWorst: {worst:0.5f}@{worst_idx}")


asyncio.run(main())
