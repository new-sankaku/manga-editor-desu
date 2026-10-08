"""口が共通で使う依存：利用者の受け取り・権限の確認・行の写し。"""


from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client

from v3server.database_engine import session_scope
from v3server.openfga_permissions import Authz
from v3server.request_actor import Actor
from v3server.server_settings import get_settings
from v3server.v3_error_types import Forbidden

# ---------------------------------------------------------------- 依存


# 管理者の権限を持つ対象（つなぎ先の登録など、作品をまたぐ操作）
SYSTEM_OBJ = "system:main"


def get_authz(request: Request) -> Authz:
    return request.app.state.authz


def get_temporal(request: Request) -> Client:
    return request.app.state.temporal


async def current_actor(x_v3_user: Annotated[str | None, Header()] = None) -> Actor:
    """ログインが入るまでの間の仮。V3_DEV_AUTH=1 のときだけ X-V3-User をそのまま利用者にする。"""
    if get_settings().dev_auth != "1":
        raise HTTPException(401, "ログインの仕組みがまだ無い。開発では V3_DEV_AUTH=1 と X-V3-User を使う")
    if not x_v3_user:
        raise HTTPException(401, "X-V3-User が無い")
    return Actor(kind="human", id=x_v3_user)


SessionDep = Annotated[AsyncSession, Depends(session_scope)]
AuthzDep = Annotated[Authz, Depends(get_authz)]
TemporalDep = Annotated[Client, Depends(get_temporal)]
ActorDep = Annotated[Actor, Depends(current_actor)]


async def require(authz: Authz, actor: Actor, relation: str, obj: str) -> None:
    if not await authz.check(actor.permission_user, relation, obj):
        raise Forbidden(f"{actor.permission_user} に {obj} の {relation} が無い")


def row(obj, *fields: str) -> dict[str, Any]:
    return {f: getattr(obj, f) for f in fields}
