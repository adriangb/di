import sys
import time

import anyio
from dependency_injector import containers, providers
from dependency_injector.wiring import Provide, inject


async def coroutine1():
    await anyio.sleep(1)
    return 1


async def coroutine2():
    await anyio.sleep(1)
    return 2


class Container(containers.DeclarativeContainer):
    coroutine1 = providers.Coroutine(coroutine1)
    coroutine2 = providers.Coroutine(coroutine2)


@inject
async def collector(
    v1: int = Provide[Container.coroutine1], v2: int = Provide[Container.coroutine2]
):
    return v1 + v2


async def main():
    container = Container()
    start = time.time()
    container.wire(modules=[sys.modules[__name__]])
    await collector()
    print(time.time() - start)


if __name__ == "__main__":
    anyio.run(main)
