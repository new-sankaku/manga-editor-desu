"""画面から呼ぶ口の組み立て。`uv run uvicorn v3server.http_routes.http_app_factory:app`

正本を変えるのは /works/{id}/ops と取り消しだけ。どちらも操作の窓口（operations/operation_submit_and_undo.py）を通る。"""


from contextlib import asynccontextmanager
from datetime import datetime

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from temporalio.client import Client

from v3server.database_engine import get_sessionmaker
from v3server.http_routes import (
    ai_job_routes,
    export_routes,
    image_file_routes,
    image_generation_routes,
    job_routes,
    lock_routes,
    name_check_routes,
    name_proposal_routes,
    pen_stroke_routes,
    service_routes,
    settings_and_search_routes,
    work_routes,
)
from v3server.http_routes.request_size_limit import RequestSizeLimit
from v3server.openfga_permissions import open_authz
from v3server.server_settings import get_settings
from v3server.v3_error_types import (
    AiInvolvementRefused,
    FixedByPerson,
    Forbidden,
    HumanHandProtected,
    Invalid,
    Locked,
    NotFound,
    NotUndoable,
    QueueNotRunning,
    UndoConflictError,
    V3Error,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with get_sessionmaker()() as session:
        app.state.authz = await open_authz(session)
    app.state.temporal = await Client.connect(get_settings().temporal_address)
    yield


app = FastAPI(title="V3 サーバー", lifespan=lifespan)
app.add_middleware(RequestSizeLimit)

_STATUS = {NotFound: 404, Forbidden: 403, Locked: 409, NotUndoable: 409, Invalid: 422, HumanHandProtected: 409,
           AiInvolvementRefused: 409, FixedByPerson: 409, QueueNotRunning: 503, UndoConflictError: 409}


@app.exception_handler(V3Error)
async def v3_error(request: Request, exc: V3Error):
    return JSONResponse(status_code=_STATUS.get(type(exc), 400),
                        content={"code": exc.code, "detail": str(exc), **(exc.extra or {})})


for _routes in (work_routes, lock_routes, job_routes, service_routes, name_proposal_routes, image_file_routes,
                name_check_routes, pen_stroke_routes, export_routes, settings_and_search_routes, ai_job_routes,
                image_generation_routes):
    app.include_router(_routes.router)

# 画像生成の画面（v3/web/）。同じ住所から配るので、画面の fetch は CORS なしで口を呼べる。認証は開発用の見出し X-V3-User
WEB_DIR = Path(__file__).resolve().parents[4] / "web"
app.mount("/web", StaticFiles(directory=WEB_DIR, html=True), name="web")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "time": datetime.now().isoformat()}
