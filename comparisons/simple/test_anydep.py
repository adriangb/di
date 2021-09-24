import time

import anyio
from di.container import Container
from di.models import Dependant
from di.params import Depends


async def coroutine1():
    await anyio.sleep(1)
    return 1


async def coroutine2():
    await anyio.sleep(1)
    return 2


async def collector(v1: int = Depends(coroutine1), v2: int = Depends(coroutine2)):
    return v1 + v2


async def main():
    container = Container()
    start = time.time()
    async with container.enter_global_scope("app"):
        await container.execute(Dependant(collector))
    print(time.time() - start)


if __name__ == "__main__":
    anyio.run(main)
