"""P54: v3/server の current_actor（X-V3-User を受ける依存関数）を、OIDC のトークン検証に置き換えられるかの試作。

v3/server/src/v3server/api/app.py の current_actor と同じ形（Actor(kind="human", id=...) を返す依存関数）にしてある。
v3/server のソースは直さない。ここは別のアプリで、置き換え先の形だけを確かめる。

確かめること
- Authorization: Bearer <JWT> の署名を、発行元（Keycloak / Hydra）の公開鍵（JWKS）で検証できるか
- iss・exp・aud を見て、別の鍵で署名したもの・改ざん・期限切れ・宛先違いを断れるか
- 取り出した sub を Actor.id に入れ、OpenFGA の user として使える形か

環境変数
  P54_ISSUER      発行元の URL（iss と一致させる）
  P54_JWKS_URL    公開鍵の URL（空なら <issuer>/.well-known/openid-configuration の jwks_uri）
  P54_AUDIENCE    空でなければ aud にこれが含まれることを求める
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Annotated

import httpx
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from jwt import PyJWKClient

ISSUER = os.environ["P54_ISSUER"]
AUDIENCE = os.environ.get("P54_AUDIENCE") or None
_jwks_url = os.environ.get("P54_JWKS_URL") or httpx.get(
    ISSUER.rstrip("/") + "/.well-known/openid-configuration", timeout=10).json()["jwks_uri"]
_jwk_client = PyJWKClient(_jwks_url, cache_keys=True, lifespan=300)


@dataclass(frozen=True)
class Actor:
    kind: str
    id: str


async def current_actor(authorization: Annotated[str | None, Header()] = None) -> Actor:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Authorization: Bearer が無い")
    token = authorization.split(" ", 1)[1].strip()
    try:
        key = _jwk_client.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token, key, algorithms=["RS256", "ES256"], issuer=ISSUER, audience=AUDIENCE,
            options={"require": ["exp", "iss", "sub"], "verify_aud": AUDIENCE is not None},
        )
    except Exception as e:  # 検証に通らないものは理由を返して 401
        raise HTTPException(401, f"トークンを検証できない: {type(e).__name__}") from e
    return Actor(kind="human", id=claims["sub"])


app = FastAPI()


@app.get("/whoami")
async def whoami(actor: Annotated[Actor, Depends(current_actor)]):
    return {"kind": actor.kind, "id": actor.id, "openfga_user": f"user:{actor.id}"}
