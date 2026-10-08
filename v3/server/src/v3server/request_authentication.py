"""だれが呼んだかを決める（V3サーバーの土台 1.3・1.4.1）。

V3_AUTH_MODE で方式を1つ選ぶ。選んだ方式で決められなければ 401 にする。別の方式で受け直すことはしない。
- oidc: Keycloak でログインする。
  - 画面: /auth/login → Keycloak → /auth/callback で、署名したクッキー（セッション）に利用者を入れる。
    クッキーで書き換えの口（GET 以外）を呼ぶときは、見出し X-V3-Request: 1 も要る（よそのページからの送信を断るため）。
  - スクリプト: Authorization: Bearer <Keycloak のアクセストークン>。署名・発行元・宛先・期限を確かめる。
  - 利用者の ID は Keycloak の sub。OpenFGA では user:<sub> になる。
- dev_header: 開発と試験だけ。X-V3-User の値をそのまま利用者にする。名前を書き換えれば誰にでもなれる。
  本番のイメージでは起動しない（V3_FORBID_DEV_HEADER=1）。使っている間は起動時に警告を出し、全部の応答に
  見出し X-V3-Auth-Mode: dev_header を付け、GET /health にも出す。
"""

import asyncio
import logging
import time
from functools import lru_cache
from typing import Annotated, Any

import httpx
import jwt
from fastapi import Header, HTTPException, Request

from v3server.request_actor import Actor
from v3server.server_settings import Settings, get_settings

log = logging.getLogger(__name__)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
DEV_MODE_WARNING = "V3_AUTH_MODE=dev_header：X-V3-User の値をそのまま利用者にしている。開発と試験の外では使わない"


@lru_cache
def oidc_metadata(discovery_url: str) -> dict[str, Any]:
    """発行元の設定（.well-known/openid-configuration）。読めなければ止める。"""
    r = httpx.get(discovery_url, timeout=10)
    r.raise_for_status()
    return r.json()


@lru_cache
def _jwk_client(jwks_uri: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(jwks_uri, cache_keys=True, lifespan=300)


def verify_access_token(token: str, s: Settings) -> dict[str, Any]:
    """Keycloak のアクセストークンを確かめて中身を返す。通らなければ jwt の例外。"""
    assert s.oidc_discovery_url and s.oidc_issuer and s.oidc_client_id  # 設定の読み込みで確かめてある
    key = _jwk_client(oidc_metadata(s.oidc_discovery_url)["jwks_uri"]).get_signing_key_from_jwt(token).key
    return jwt.decode(token, key, algorithms=["RS256"], issuer=s.oidc_issuer, audience=s.oidc_client_id,
                      options={"require": ["exp", "iss", "sub", "aud"]})


def session_user(request: Request) -> dict[str, Any] | None:
    """クッキーのセッションにいる利用者。期限を過ぎていれば消して None。"""
    user = request.session.get("user")
    if user is None:
        return None
    if user["expires_at"] < time.time():
        request.session.clear()
        return None
    return user


async def current_actor(
    request: Request,
    x_v3_user: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> Actor:
    s = get_settings()
    if s.auth_mode == "dev_header":
        if not x_v3_user:
            raise HTTPException(401, "X-V3-User が無い（V3_AUTH_MODE=dev_header）")
        return Actor(kind="human", id=x_v3_user)

    if authorization is not None:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(401, "Authorization は Bearer <トークン> の形で送る")
        try:
            claims = await asyncio.to_thread(verify_access_token, token.strip(), s)
        except jwt.PyJWTError as e:
            raise HTTPException(401, f"トークンを確かめられない: {type(e).__name__}") from e
        return Actor(kind="human", id=claims["sub"])

    user = session_user(request)
    if user is None:
        raise HTTPException(401, "ログインしていない（/auth/login）")
    if request.method not in SAFE_METHODS and request.headers.get("x-v3-request") != "1":
        raise HTTPException(403, "クッキーで書き換えるときは見出し X-V3-Request: 1 が要る")
    return Actor(kind="human", id=user["sub"])
