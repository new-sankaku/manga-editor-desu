"""ログイン・ログアウト・自分が誰か（V3サーバーの土台 1.4.1）。OIDC の手順は Authlib に任せる。

- GET /auth/mode    ログインの方式（ログイン前の画面が、名前の欄を出すかログインへ行くかを決める）
- GET /auth/me      自分の ID（OpenFGA の user:<ID> の ID）・名前・メール
- GET /auth/login   Keycloak のログインの画面へ（認可コード＋PKCE）。?next=/web/ で戻る先
- GET /auth/callback Keycloak から戻る。ID トークンを確かめて、セッションに利用者を入れる
- GET /auth/logout  セッションを消し、Keycloak のセッションも終える
"""

import time
from typing import Annotated, Any
from urllib.parse import urlencode

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from v3server.request_actor import Actor
from v3server.request_authentication import current_actor
from v3server.server_settings import get_settings

router = APIRouter(prefix="/auth")

_oauth: OAuth | None = None


def _client() -> Any:
    global _oauth
    s = get_settings()
    if s.auth_mode != "oidc":
        raise HTTPException(404, "V3_AUTH_MODE=oidc のときだけ使える")
    if _oauth is None:
        _oauth = OAuth()
        _oauth.register(
            "keycloak", client_id=s.oidc_client_id, client_secret=s.oidc_client_secret,
            server_metadata_url=s.oidc_discovery_url,
            client_kwargs={"scope": "openid profile email", "code_challenge_method": "S256"},
        )
    return _oauth.create_client("keycloak")


def _safe_next(next_path: str | None) -> str:
    """戻る先はこのサーバーの中の住所だけ（よそのサイトへ飛ばす口にしない）。"""
    if next_path and next_path.startswith("/") and not next_path.startswith("//") and "\\" not in next_path:
        return next_path
    return "/web/"


@router.get("/mode")
async def mode() -> dict[str, str]:
    return {"mode": get_settings().auth_mode}


@router.get("/me")
async def me(request: Request, actor: Annotated[Actor, Depends(current_actor)]) -> dict[str, Any]:
    out: dict[str, Any] = {"mode": get_settings().auth_mode, "id": actor.id, "openfga_user": f"user:{actor.id}"}
    if get_settings().auth_mode == "oidc":
        user = request.session.get("user") or {}
        out |= {"name": user.get("name"), "email": user.get("email")}
    return out


@router.get("/login")
async def login(request: Request, next: str | None = None):
    client = _client()
    request.session["next"] = _safe_next(next)
    return await client.authorize_redirect(request, f"{get_settings().public_url}/auth/callback")


@router.get("/callback")
async def callback(request: Request):
    client = _client()
    token = await client.authorize_access_token(request)
    info = token["userinfo"]
    s = get_settings()
    assert s.session_max_age_seconds is not None  # 設定の読み込みで確かめてある
    request.session["user"] = {
        "sub": info["sub"], "name": info.get("preferred_username"), "email": info.get("email"),
        "expires_at": time.time() + s.session_max_age_seconds,
        "id_token": token["id_token"],
    }
    return RedirectResponse(request.session.pop("next", "/web/"), status_code=303)


@router.get("/logout")
async def logout(request: Request):
    client = _client()
    user = request.session.get("user") or {}
    request.session.clear()
    metadata = await client.load_server_metadata()
    params = {"post_logout_redirect_uri": f"{get_settings().public_url}/web/",
              "client_id": get_settings().oidc_client_id, "id_token_hint": user.get("id_token")}
    query = urlencode({k: v for k, v in params.items() if v})
    return RedirectResponse(f"{metadata['end_session_endpoint']}?{query}", status_code=303)
