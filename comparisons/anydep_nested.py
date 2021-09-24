import asyncio
from time import time

from di.container import Container
from di.models import Dependant
from di.params import Depends  # noqa

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


async def test(container: Container):
    r = await container.execute(Dependant(final))  # type: ignore
    assert r == 1


async def main():
    container = Container()
    t = []
    async with container.enter_global_scope("app"):
        for _ in range(ITER):  # 10 incoming requests
            async with container.enter_local_scope("request"):
                start = time()
                await test(container)
            t.append(time() - start)
    assert counter["counter"] == NESTING * ITER
    average = sum(t) / len(t)
    worst = max(t)
    worst_idx = t.index(worst)
    print(f"Average: {average:0.5f}\nWorst: {worst:0.5f}@{worst_idx}")


asyncio.run(main())
