"""画面から呼ぶ口の組み立て。`uv run uvicorn v3server.http_routes.http_app_factory:app`

正本を変えるのは /works/{id}/ops と取り消しだけ。どちらも操作の窓口（operations/operation_submit_and_undo.py）を通る。"""


from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from temporalio.client import Client

from v3server.database_engine import get_sessionmaker
from v3server.http_routes import (
    image_file_routes,
    job_routes,
    lock_routes,
    name_proposal_routes,
    service_routes,
    work_routes,
)
from v3server.openfga_permissions import open_authz
from v3server.server_settings import get_settings
from v3server.v3_error_types import (
    Forbidden,
    HumanHandProtected,
    Invalid,
    Locked,
    NotFound,
    NotUndoable,
    V3Error,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with get_sessionmaker()() as session:
        app.state.authz = await open_authz(session)
    app.state.temporal = await Client.connect(get_settings().temporal_address)
    yield


app = FastAPI(title="V3 サーバー", lifespan=lifespan)

_STATUS = {NotFound: 404, Forbidden: 403, Locked: 409, NotUndoable: 409, Invalid: 422, HumanHandProtected: 409}


@app.exception_handler(V3Error)
async def v3_error(request: Request, exc: V3Error):
    return JSONResponse(status_code=_STATUS.get(type(exc), 400), content={"code": exc.code, "detail": str(exc)})


for _routes in (work_routes, lock_routes, job_routes, service_routes, name_proposal_routes, image_file_routes):
    app.include_router(_routes.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "time": datetime.now().isoformat()}
