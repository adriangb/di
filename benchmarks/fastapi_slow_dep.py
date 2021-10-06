"""Test dependency resolution using a complex DAG
"""

import time

import anyio
import httpx

# note: because FastAPI has a pinned starlette version, it needs to be pip installed manually
from fastapi import Depends  # type: ignore
from fastapi import FastAPI as App  # type: ignore
from fastapi import Response


async def slow1() -> None:
    await anyio.sleep(0.1)


async def slow2() -> None:
    await anyio.sleep(0.1)


async def root(one: None = Depends(slow1), two: None = Depends(slow2)) -> None:
    ...


app = App()


@app.get("/")
async def endpoint(dag: None = Depends(root)):
    return Response()


async def main():
    async with httpx.AsyncClient(app=app, base_url="http://testclient") as client:
        iterations = 10
        start = time.time()
        for _ in range(iterations):
            await client.get("/")
        elapsed = time.time() - start
        print(f"{iterations/elapsed:2f} req/sec")


if __name__ == "__main__":
    anyio.run(main)
