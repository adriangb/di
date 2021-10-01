"""Test dependency resolution using a complex DAG
"""

import time

from starlette.responses import Response
from starlette.testclient import TestClient

from benchmarks.utils import generate_dag
from di import Depends
from docs.src.starlette.src import App

root = generate_dag(Depends, 4, 3, 3)


app = App()


@app.get("/")
async def endpoint(dag: None = Depends(root)):
    return Response()


with TestClient(app) as client:
    start = time.time()
    for _ in range(50):
        client.get("/")
    print(f"{time.time()-start}")
