"""画面から呼ぶ口の組み立て。`uv run uvicorn v3server.http_routes.http_app_factory:app`

正本を変えるのは /works/{id}/ops と取り消しだけ。どちらも操作の窓口（operations/operation_submit_and_undo.py）を通る。"""


import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from psycopg.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send
from temporalio.client import Client

from v3server.database_engine import get_sessionmaker
from v3server.health_checks import readiness
from v3server.http_routes import (
    ai_job_routes,
    export_routes,
    harness_routes,
    image_file_routes,
    image_generation_routes,
    job_routes,
    lock_routes,
    login_routes,
    name_check_routes,
    name_proposal_routes,
    page_assignment_and_preview_routes,
    pen_stroke_routes,
    service_inspection_and_set_routes,
    service_routes,
    settings_and_search_routes,
    text_typeset_routes,
    translation_review_import_routes,
    work_routes,
)
from v3server.http_routes.request_size_limit import RequestSizeLimit
from v3server.image_file_storage import image_store
from v3server.messages import Message, current_lang, m, render, render_tree, request_lang, set_current_lang, text_of
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
    UndoConflictError,
    V3Error,
)

log = logging.getLogger(__name__)
# 包んだ文（ms()）の開く印を UTF-8 にした物
PACKED_MARK = "\ue000".encode()


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


class LocalizedJSONResponse(JSONResponse):
    """返事の中の m() の文（処理の名前・項目の名前・成功の返事に入れた失敗の理由など）を、呼び出しの言語で出す。"""

    def render(self, content) -> bytes:
        lang = current_lang()
        if lang != "ja":
            return super().render(render_tree(content, lang))
        # 日本語では、包んだ文（ms()）が入っている返事だけ中をたどる（大きい返事を毎回たどらない）
        body = super().render(content)
        return super().render(render_tree(content, lang)) if PACKED_MARK in body else body


class RequestLanguage:
    """呼び出しの言語（X-V3-Lang）を、その呼び出しの間だけ覚える。返事を作る所（上の LocalizedJSONResponse）が読む。"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            set_current_lang(request_lang(Headers(scope=scope)))
        await self.app(scope, receive, send)


app = FastAPI(title="V3 サーバー", lifespan=lifespan, default_response_class=LocalizedJSONResponse)  # i18n:dev
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
# 最後に足した物がいちばん外で動く。本体の大きさの上限は、ログインの確かめより前に止める
app.add_middleware(RequestSizeLimit)
app.add_middleware(RequestLanguage)

_STATUS = {NotFound: 404, Forbidden: 403, Locked: 409, NotUndoable: 409, Invalid: 422, HumanHandProtected: 409,
           AiInvolvementRefused: 409, FixedByPerson: 409, QueueNotRunning: 503, UndoConflictError: 409}


@app.exception_handler(V3Error)
async def v3_error(request: Request, exc: V3Error):
    # 失敗の文は、呼び出しの言語（X-V3-Lang）で出す。m() で作っていない文はそのまま出る（v3server/messages.py）
    detail = render(text_of(exc), request_lang(request.headers))
    return JSONResponse(status_code=_STATUS.get(type(exc), 400),
                        content={"code": exc.code, "detail": detail, **(exc.extra or {})})


@app.exception_handler(IntegrityError)
async def duplicate_key(request: Request, exc: IntegrityError):
    """同じ id の物をもう一度作ろうとした時（同じ操作を送り直した時など）は 409 を返す。
    ほかの食い違い（参照先が無いなど）はプログラムの誤りなので、500 のままにする。"""
    if not isinstance(exc.orig, UniqueViolation):
        raise exc
    detail = render(m("すでに同じものがある（{name}）", name=exc.orig.diag.constraint_name or ""), request_lang(request.headers))
    return JSONResponse(status_code=409, content={"code": "already_exists", "detail": detail})


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    """HTTPException の文も、呼び出しの言語で出す（中身は FastAPI の既定の返事と同じ）。"""
    exc.detail = render(exc.detail, request_lang(request.headers))
    return await http_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    """入力の確かめ（pydantic）で、こちらの決まりに掛かった文を、呼び出しの言語で出す。

    pydantic は確かめの中の ValueError を「Value error, 文」にして返す。元の例外が m() の文を持っていれば、その文に差し替える。
    型の違いなど pydantic が作る文（英語）は、そのまま返す。"""
    lang, errors = request_lang(request.headers), []
    for error in exc.errors():
        cause = (error.get("ctx") or {}).get("error")
        text = text_of(cause) if isinstance(cause, BaseException) else None
        errors.append({**error, "msg": render(text, lang)} if isinstance(text, Message) else error)
    # 確かめの中で ms() の文を投げた時は、pydantic が作った文の中に包んだ文が入っている。全部を文に戻す
    return JSONResponse(status_code=422, content={"detail": render_tree(jsonable_encoder(errors), lang)})


for _routes in (login_routes, work_routes, lock_routes, job_routes, service_routes, name_proposal_routes, image_file_routes,
                name_check_routes, pen_stroke_routes, export_routes, settings_and_search_routes, ai_job_routes,
                image_generation_routes, translation_review_import_routes, page_assignment_and_preview_routes,
                service_inspection_and_set_routes, text_typeset_routes, harness_routes):
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
    """DB・OpenFGA・Temporal・絵の置き場・ワーカーに届くか。1つでも届かなければ 503。"""
    result = await readiness(request.app.state.temporal)
    return JSONResponse(status_code=200 if result["ok"] else 503, content=result)
