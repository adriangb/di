"""Test dependency resolution using a complex DAG
"""

import time

import anyio
import httpx
from starlette.responses import Response

from benchmarks.utils import generate_dag
from di import Depends
from docs.src.starlette.src import App

root = generate_dag(Depends, 4, 3, 3)


app = App()


@app.get("/")
async def endpoint(dag: None = Depends(root)):
    return Response()


async def main():
    async with httpx.AsyncClient(app=app, base_url="http://testclient") as client:
        iterations = 1000
        start = time.time()
        for _ in range(iterations):
            await client.get("/")
        elapsed = time.time() - start
        print(f"{iterations/elapsed:2f} req/sec")


if __name__ == "__main__":
    anyio.run(main)
