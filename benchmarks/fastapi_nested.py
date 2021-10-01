"""Test dependency resolution using a complex DAG
"""

import time

# note: because FastAPI has a pinned starlette version, it needs to be pip installed manually
from fastapi import Depends  # type: ignore
from fastapi import FastAPI as App  # type: ignore
from starlette.responses import Response
from starlette.testclient import TestClient

from benchmarks.utils import generate_dag

root = generate_dag(Depends, 15, 5, 3)


app = App()


@app.get("/")
async def endpoint(dag: None = Depends(root)):
    return Response()


with TestClient(app) as client:
    start = time.time()
    for _ in range(2):
        client.get("/")
    print(f"{time.time()-start}")
