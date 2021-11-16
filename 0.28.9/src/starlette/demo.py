from dataclasses import dataclass

from starlette.requests import Request
from starlette.responses import Response
from starlette.testclient import TestClient

from di import Depends
from docs.src.starlette.src import App

app = App()


@dataclass
class Config:
    host: str = "localhost"  # could be loaded from env vars


@dataclass
class DBConnection:
    config: Config

    async def execute(self, stmt: str) -> None:
        print(f"Executing on {self.config.host}: {stmt}")


@app.get("/test")
async def route(request: Request, conn: DBConnection = Depends(scope="app")):
    await conn.execute((await request.body()).decode())
    return Response()


def main() -> None:
    with TestClient(app) as client:
        res = client.get("/test", data=b"SELECT 1")
        assert res.status_code == 200
