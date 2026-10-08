"""依頼（順番待ち）の口。"""


from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from v3server.v3_error_types import Invalid, NotFound

# ---------------------------------------------------------------- 依頼（順番待ち）


router = APIRouter()


class NewJob(BaseModel):
    process: str
    request: dict[str, Any]
    page_id: str | None = None


JOB_FIELDS = ("id", "service_id", "process", "page_id", "requested_by", "requested_via", "status", "failure_kind",
              "failure_detail", "request", "result", "created_at", "updated_at")


async def _job_in_work(session: AsyncSession, work_id: str, job_id: str) -> Job:
    job = await session.get(Job, job_id)
    if job is None or job.work_id != work_id:
        raise NotFound(f"jobs:{job_id}")
    return job


@router.post("/works/{work_id}/jobs", status_code=201)
async def create_job(work_id: str, body: NewJob, session: SessionDep, authz: AuthzDep, temporal: TemporalDep,
                     actor: ActorDep):
    job = await job_start_and_control.enqueue(session, authz, temporal, actor, work_id, body.process, body.request, "human",
                                body.page_id)
    return row(job, *JOB_FIELDS)


@router.get("/works/{work_id}/jobs")
async def list_jobs(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """進捗一覧の元。止まったもの・待っているものも出す。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    rows = (
        await session.execute(select(Job).where(Job.work_id == work_id).order_by(Job.created_at))
    ).scalars().all()
    return [row(j, *JOB_FIELDS) for j in rows]


@router.post("/works/{work_id}/jobs/{job_id}/cancel", status_code=202)
async def cancel_job(work_id: str, job_id: str, session: SessionDep, authz: AuthzDep, temporal: TemporalDep,
                     actor: ActorDep):
    job = await _job_in_work(session, work_id, job_id)
    if job.requested_by != actor.id:
        await require(authz, actor, "can_manage", work_obj(work_id))
    await job_start_and_control.cancel(temporal, job)


@router.post("/works/{work_id}/jobs/{job_id}/resume", status_code=202)
async def resume_job(work_id: str, job_id: str, session: SessionDep, authz: AuthzDep, temporal: TemporalDep,
                     actor: ActorDep):
    await require(authz, actor, "can_manage", work_obj(work_id))
    await job_start_and_control.resume(temporal, await _job_in_work(session, work_id, job_id))


@router.post("/works/{work_id}/jobs/{job_id}/retry", status_code=201)
async def retry_job(work_id: str, job_id: str, session: SessionDep, authz: AuthzDep, temporal: TemporalDep,
                    actor: ActorDep):
    """止まったものの「もう一度」。いまの処理ごとの送り先へ、同じ中身で新しく頼む。"""
    job = await _job_in_work(session, work_id, job_id)
    if job.status != "stopped":
        raise Invalid("止まったものだけもう一度頼める")
    new_job = await job_start_and_control.enqueue(session, authz, temporal, actor, work_id, job.process, job.request, "human",
                                    job.page_id)
    return row(new_job, *JOB_FIELDS)
