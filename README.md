# AnyDep

WIP.

A dependency injection framework based on:

- Type annotations for inference of types
- Anyio compatibility
- Arbitrary nested scoping for value caching & lifetimes
- Lifetimes for generator context managers (i.e. an AsyncExitStack for each scope)
- Explicit building of a task DAG & parallel execution
- Concurrency for sync function by executing them in a ThreadPool


Sample:

```python
from typing import AsyncGenerator, Dict, Generator, Union

import anyio

from anydep.container import Container
from anydep.params import Depends


async def async_call() -> int:
    return 1

async def async_gen() -> AsyncGenerator[int, None]:
    yield 2

def sync_call() -> int:
    return 3

def sync_gen() -> Generator[int, None, None]:
    yield 4

class Class:
    def __init__(self) -> None:
        self.value = 5

def collector(
    v5: Class,
    v1: int = Depends(async_call),
    v2: int = Depends(async_gen),
    v3: int = Depends(sync_call),
    v4: int = Depends(sync_gen),
) -> int:
    return v1 + v2 + v3 + v4 + v5.value


async def main():
    container = Container()
    async with container.enter_scope("app"):
        assert (await container.resolve(collector)) == 15

anyio.run(main())
```
