"""ログインの方式と設定の確かめ（request_authentication.py・server_settings.py）。
本物の Keycloak を通す確かめは deploy/check_production_stack.py（V3サーバーの土台 8章）。"""

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from v3server import request_authentication as ra
from v3server.server_settings import Settings

BASE = {"database_url": "postgresql+psycopg://x/y", "temporal_address": "t:1", "openfga_url": "http://f",
        "litellm_url": "http://l", "lock_ttl_seconds": 900, "node_executable": "node", "image_store": "local",
        "image_dir": "/tmp/x", "OPENFGA_PRESHARED_KEY": "k", "request_max_bytes": 1024, "image_max_pixels": 1024,
        "psd_max_layers": 10}
OIDC = {"auth_mode": "oidc", "oidc_issuer": "https://auth.example/realms/v3",
        "oidc_discovery_url": "http://keycloak:8080/realms/v3/.well-known/openid-configuration",
        "oidc_client_id": "v3-server", "oidc_client_secret": "s", "public_url": "https://manga.example",
        "session_secret": "k" * 32, "session_max_age_seconds": 3600}


def settings(**kw) -> Settings:
    return Settings(_env_file=None, **{**BASE, **kw})


def test_方式は既定が無く_選ばなければ止まる(monkeypatch):
    monkeypatch.delenv("V3_AUTH_MODE", raising=False)
    with pytest.raises(ValidationError, match="auth_mode"):
        settings()


def test_oidcは要る値が欠けると止まる():
    with pytest.raises(ValidationError, match="V3_SESSION_SECRET"):
        settings(**{**OIDC, "session_secret": ""})
    assert settings(**OIDC).auth_mode == "oidc"


def test_本番のイメージでは開発用の名乗り方で起動しない():
    with pytest.raises(ValidationError, match="dev_header を使えない"):
        settings(auth_mode="dev_header", forbid_dev_header=True)
    assert settings(auth_mode="oidc", forbid_dev_header=True, **{k: v for k, v in OIDC.items() if k != "auth_mode"})


def test_s3の置き場は要る値が欠けると止まる():
    with pytest.raises(ValidationError, match="V3_S3_BUCKET"):
        settings(auth_mode="dev_header", image_store="s3", s3_endpoint_url="http://s3", s3_region="r",
                 s3_access_key_id="a", s3_secret_access_key="b")


# ---------------------------------------------------------------- Bearer のトークン

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def token(key=KEY, **claims) -> str:
    body = {"iss": OIDC["oidc_issuer"], "aud": "v3-server", "sub": "kc-sub-1", "exp": int(time.time()) + 60} | claims
    return jwt.encode(body, key, algorithm="RS256")


@pytest.fixture
def oidc(monkeypatch):
    s = settings(**OIDC)
    monkeypatch.setattr(ra, "get_settings", lambda: s)
    monkeypatch.setattr(ra, "oidc_metadata", lambda url: {"jwks_uri": "http://keycloak/jwks"})
    monkeypatch.setattr(ra, "_jwk_client",
                        lambda uri: SimpleNamespace(get_signing_key_from_jwt=lambda t: SimpleNamespace(
                            key=KEY.public_key())))
    return s


def request(method="GET", session=None, headers=()) -> Request:
    scope = {"type": "http", "method": method, "headers": [(k.encode(), v.encode()) for k, v in headers],
             "session": {} if session is None else session}
    return Request(scope)


async def test_正しいトークンは_subを利用者にする(oidc):
    actor = await ra.current_actor(request(), None, f"Bearer {token()}")
    assert actor.id == "kc-sub-1" and actor.permission_user == "kc-sub-1"


@pytest.mark.parametrize("bad", [
    {"key": OTHER_KEY}, {"iss": "https://evil.example"}, {"aud": "other-client"}, {"exp": int(time.time()) - 5},
])
async def test_別の鍵_発行元違い_宛先違い_期限切れは401(oidc, bad):
    key = bad.pop("key", KEY)
    with pytest.raises(HTTPException) as e:
        await ra.current_actor(request(), None, f"Bearer {token(key, **bad)}")
    assert e.value.status_code == 401


async def test_oidcでは見出しで名乗っても通らない(oidc):
    with pytest.raises(HTTPException) as e:
        await ra.current_actor(request(), "admin", None)
    assert e.value.status_code == 401


async def test_セッションは期限を過ぎると消え_書き換えには見出しが要る(oidc):
    live = {"user": {"sub": "kc-sub-2", "expires_at": time.time() + 60}}
    assert (await ra.current_actor(request(session=live), None, None)).id == "kc-sub-2"
    with pytest.raises(HTTPException) as e:
        await ra.current_actor(request("POST", session=live), None, None)
    assert e.value.status_code == 403
    ok = await ra.current_actor(request("POST", session=live, headers=[("x-v3-request", "1")]), None, None)
    assert ok.id == "kc-sub-2"
    old = {"user": {"sub": "kc-sub-2", "expires_at": time.time() - 1}}
    with pytest.raises(HTTPException) as e:
        await ra.current_actor(request(session=old), None, None)
    assert e.value.status_code == 401 and old == {}


async def test_開発用は見出しが無ければ401(monkeypatch):
    s = settings(auth_mode="dev_header")
    monkeypatch.setattr(ra, "get_settings", lambda: s)
    with pytest.raises(HTTPException):
        await ra.current_actor(request(), None, None)
    assert (await ra.current_actor(request(), "u1", None)).id == "u1"
