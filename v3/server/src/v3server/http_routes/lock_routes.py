"""ロックの口。"""


from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from v3server import lock_rules
from v3server.canonical_tables.event_and_lock_tables import Lock
from v3server.canonical_tables.service_and_job_tables import Job
from v3server.generation_queue import job_start_and_control
from v3server.http_routes.http_dependencies import (
    ActorDep,
    AuthzDep,
    SessionDep,
    TemporalDep,
    require,
    row,
)
from v3server.operations.operation_base import work_obj

# ---------------------------------------------------------------- ロック


router = APIRouter()


class NewLock(BaseModel):
    target_kind: Literal["page", "panel", "item"]
    target_id: str
    reason: str
    page_id: str | None = None


@router.post("/works/{work_id}/locks", status_code=201)
async def acquire_lock(work_id: str, body: NewLock, session: SessionDep, authz: AuthzDep,
                       temporal: TemporalDep, actor: ActorDep):
    result = await lock_rules.acquire(session, authz, actor, work_id, body.target_kind, body.target_id, body.reason,
                                 body.page_id)
    # 人が取り返したAIのロックの作業を止める（V3ハーネス設計 4.3）
    for job_id in result.preempted_job_ids:
        job = await session.get(Job, job_id)
        if job is not None and job.status not in ("done", "cancelled", "stopped"):
            await job_start_and_control.cancel(temporal, job)
    return {"id": result.lock.id, "expires_at": result.lock.expires_at,
            "preempted_job_ids": result.preempted_job_ids}


@router.delete("/works/{work_id}/locks/{lock_id}", status_code=204)
async def release_lock(work_id: str, lock_id: str, session: SessionDep, actor: ActorDep):
    await lock_rules.release(session, actor, work_id, lock_id)


@router.get("/works/{work_id}/locks")
async def list_locks(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    rows = (await session.execute(select(Lock).where(Lock.work_id == work_id))).scalars().all()
    return [row(lk, "id", "target_kind", "target_id", "page_id", "holder_kind", "holder_id", "reason", "job_id",
                "expires_at") for lk in rows]
