"""口が共通で使う依存：利用者の受け取り・権限の確認・行の写し。"""


from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client

from v3server.database_engine import session_scope
from v3server.openfga_permissions import Authz
from v3server.request_actor import Actor
from v3server.request_authentication import current_actor
from v3server.v3_error_types import Forbidden

# ---------------------------------------------------------------- 依存


# 管理者の権限を持つ対象（つなぎ先の登録など、作品をまたぐ操作）
SYSTEM_OBJ = "system:main"


def get_authz(request: Request) -> Authz:
    return request.app.state.authz


def get_temporal(request: Request) -> Client:
    return request.app.state.temporal


SessionDep = Annotated[AsyncSession, Depends(session_scope)]
AuthzDep = Annotated[Authz, Depends(get_authz)]
TemporalDep = Annotated[Client, Depends(get_temporal)]
ActorDep = Annotated[Actor, Depends(current_actor)]


async def require(authz: Authz, actor: Actor, relation: str, obj: str) -> None:
    if not await authz.check(actor.permission_user, relation, obj):
        raise Forbidden(f"{actor.permission_user} に {obj} の {relation} が無い")


def row(obj, *fields: str) -> dict[str, Any]:
    return {f: getattr(obj, f) for f in fields}
