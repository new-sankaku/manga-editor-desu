"""画面から呼ぶ口の組み立て。`uv run uvicorn v3server.http_routes.http_app_factory:app`

正本を変えるのは /works/{id}/ops と取り消しだけ。どちらも操作の窓口（operations/operation_submit_and_undo.py）を通る。"""


import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware
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
    login_routes,
    name_check_routes,
    name_proposal_routes,
    pen_stroke_routes,
    service_routes,
    settings_and_search_routes,
    work_routes,
)
from v3server.health_checks import readiness
from v3server.image_file_storage import image_store
from v3server.openfga_permissions import open_authz
from v3server.request_authentication import DEV_MODE_WARNING
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
    V3Error,
)


log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().auth_mode == "dev_header":
        log.warning(DEV_MODE_WARNING)
    # 絵の置き場に届かなければ起動しない（使う時になって初めて止まるのを避ける）
    image_store().check()
    async with get_sessionmaker()() as session:
        app.state.authz = await open_authz(session)
    app.state.temporal = await Client.connect(get_settings().temporal_address)
    yield


app = FastAPI(title="V3 サーバー", lifespan=lifespan)
_settings = get_settings()
if _settings.auth_mode == "oidc":
    assert _settings.session_secret and _settings.public_url  # 設定の読み込みで確かめてある
    app.add_middleware(SessionMiddleware, secret_key=_settings.session_secret, session_cookie="v3_session",
                       same_site="lax", https_only=_settings.public_url.startswith("https://"),
                       max_age=_settings.session_max_age_seconds)
else:
    @app.middleware("http")
    async def mark_dev_auth(request: Request, call_next):
        """開発用の名乗り方で動いていることを、全部の応答に出す。"""
        response = await call_next(request)
        response.headers["X-V3-Auth-Mode"] = "dev_header"
        return response

_STATUS = {NotFound: 404, Forbidden: 403, Locked: 409, NotUndoable: 409, Invalid: 422, HumanHandProtected: 409,
           AiInvolvementRefused: 409, FixedByPerson: 409, QueueNotRunning: 503}


@app.exception_handler(V3Error)
async def v3_error(request: Request, exc: V3Error):
    return JSONResponse(status_code=_STATUS.get(type(exc), 400), content={"code": exc.code, "detail": str(exc)})


for _routes in (login_routes, work_routes, lock_routes, job_routes, service_routes, name_proposal_routes, image_file_routes,
                name_check_routes, pen_stroke_routes, export_routes, settings_and_search_routes, ai_job_routes,
                image_generation_routes):
    app.include_router(_routes.router)

# 画像生成の画面（v3/web/）。同じ住所から配るので、画面の fetch は CORS なしで口を呼べる。ログインは /auth/（login_routes.py）
WEB_DIR = Path(__file__).resolve().parents[4] / "web"
app.mount("/web", StaticFiles(directory=WEB_DIR, html=True), name="web")


@app.get("/health")
async def health() -> dict[str, str]:
    """プロセスが応答するか。中身まで見るのは /health/ready。"""
    return {"status": "ok", "time": datetime.now(UTC).isoformat(), "auth_mode": get_settings().auth_mode}


@app.get("/health/ready")
async def health_ready(request: Request) -> JSONResponse:
    """DB・OpenFGA・Temporal・絵の置き場・作業者に届くか。1つでも届かなければ 503。"""
    result = await readiness(request.app.state.temporal)
    return JSONResponse(status_code=200 if result["ok"] else 503, content=result)
