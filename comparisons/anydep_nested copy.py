import asyncio
from time import time

from anydep.container import Container
from anydep.params import Depends  # noqa

tempalate = "async def func_{}({}): await asyncio.sleep(0.5);return 1"

for f in range(15):
    params = []
    if f == 14:
        for p in range(f):
            params.append(f"v{p}: int = Depends(func_{p})")
    param_code = ", ".join(params)
    code = tempalate.format(f, param_code)
    exec(code)

final = eval(f"func_{f}")


async def test(container: Container):
    r = await container.execute(container.get_dependant(final))
    assert r == 1


async def main():
    container = Container()
    t = []
    async with container.enter_global_scope("app"):
        async with container.enter_local_scope("request"):
            start = time()
            await test(container)
        t.append(time() - start)
    average = sum(t) / len(t)
    worst = max(t)
    worst_idx = t.index(worst)
    print(f"Average: {average:0.5f}\nWorst: {worst:0.5f}@{worst_idx}")


asyncio.run(main())
