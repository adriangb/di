# di: Pythonic Dependency Injection

Autowiring dependency injection.

This project is a generalization of FastAPI's dependency injection framework.

Sample:

```python
from typing import AsyncGenerator, Generator

import anyio

from di.container import Container
from di.dependency import Dependant
from di.params import Depends


async def async_call() -> int:
    return 1

async def async_gen() -> AsyncGenerator[int, None]:
    yield 2

def sync_call() -> int:
    return 3

def sync_gen() -> Generator[int, None, None]:
    yield 4

class Class:
    def __init__(self, value: int = 5) -> None:
        self.value = value

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
    dependant = Dependant(collector)
    async with container.enter_global_scope("app"):
        async with container.enter_local_scope("request"):  # localized using contextvars
            # bind an instance, class, callable, etc.; for example an incoming request
            with container.bind(lambda: Class(-10), Class, scope="request"):  # binds can be permanent or context managers
                assert (await container.execute(dependant)) == 0  # summed up to 10 but Class.value is -10
        assert (await container.execute(dependant)) == 15  # our bind was cleared since we exited the scope

anyio.run(main)
```

All the returned value will be cached within the `"app"` scope and trashed as soon as the scope is exited.
In this case, all of `collector`'s dependencies will be executed in parallel.
