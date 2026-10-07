"""画面から呼ぶ口。`uv run uvicorn v3server.api.app:app`

正本を変えるのは /works/{id}/ops と取り消しだけ。どちらも操作の窓口（ops/gateway.py）を通る。
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client

from .. import locks
from ..actor import Actor
from ..authz import Authz, Tuple, open_authz
from ..config import get_settings
from ..db import get_sessionmaker, session_scope
from ..errors import Forbidden, Invalid, Locked, NotFound, NotUndoable, V3Error
from ..models import (
    Episode,
    Event,
    Job,
    Lock,
    Page,
    Panel,
    ProcessRoute,
    Service,
    ServiceProcess,
    Threshold,
    Volume,
    Work,
    WorkDestination,
)
from ..ops import gateway
from ..ops.catalog import Op, work_obj
from ..queue import jobs as job_ops

SYSTEM_OBJ = "system:main"


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with get_sessionmaker()() as session:
        app.state.authz = await open_authz(session)
    app.state.temporal = await Client.connect(get_settings().temporal_address)
    yield


app = FastAPI(title="V3 サーバー", lifespan=lifespan)

_STATUS = {NotFound: 404, Forbidden: 403, Locked: 409, NotUndoable: 409, Invalid: 422}


@app.exception_handler(V3Error)
async def v3_error(request: Request, exc: V3Error):
    return JSONResponse(status_code=_STATUS.get(type(exc), 400), content={"code": exc.code, "detail": str(exc)})


# ---------------------------------------------------------------- 依存


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


# ---------------------------------------------------------------- 作品


class NewWork(BaseModel):
    title: str
    reading_direction: Literal["rtl", "ltr"]
    text_direction: Literal["vertical", "horizontal"]
    medium: Literal["paper", "web_page", "vertical_scroll"]
    trim_size: str | None = None
    default_page_count: int | None = None


@app.post("/works", status_code=201)
async def create_work(body: NewWork, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """作品を作った人が作者になる。作品が無い間は操作の窓口を通せないので、ここで最初の出来事を書く。"""
    work = Work(**body.model_dump())
    session.add(work)
    await session.flush()
    gateway.append_event(session, work, actor, "create_work", body.model_dump())
    tuple_ = Tuple(f"user:{actor.id}", "author", work_obj(work.id))
    await authz.write([tuple_])
    try:
        await session.commit()
    except Exception:
        await authz.write(deletes=[tuple_])
        raise
    return {"id": work.id}


@app.get("/works/{work_id}")
async def get_work(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    work = await session.get(Work, work_id)
    if work is None:
        raise NotFound(f"works:{work_id}")

    async def all_of(model):
        return (await session.execute(select(model).where(model.work_id == work_id))).scalars().all()

    return {
        "work": row(work, "id", "title", "reading_direction", "text_direction", "medium", "trim_size",
                    "default_page_count", "head_seq"),
        "volumes": [row(v, "id", "number", "title", "removed") for v in await all_of(Volume)],
        "episodes": [row(e, "id", "volume_id", "number", "title", "deadline", "removed") for e in await all_of(Episode)],
        "pages": [row(p, "id", "episode_id", "number", "removed") for p in await all_of(Page)],
        "panels": [
            row(p, "id", "page_id", "order", "frame", "role", "content", "human_confirmed", "removed")
            for p in await all_of(Panel)
        ],
        "thresholds": [row(t, "key", "value", "source", "status", "note") for t in await all_of(Threshold)],
        "destinations": [d.service_id for d in await all_of(WorkDestination)],
    }


@app.get("/works/{work_id}/members")
async def get_members(work_id: str, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    return [
        {"user": t.user.removeprefix("user:"), "role": t.relation}
        for t in await authz.read(work_obj(work_id))
        if t.user.startswith("user:")
    ]


# ---------------------------------------------------------------- 操作と出来事


@app.post("/works/{work_id}/ops")
async def submit_op(work_id: str, op: Annotated[Op, Field(discriminator="type")], session: SessionDep,
                    authz: AuthzDep, actor: ActorDep):
    event = await gateway.submit(session, authz, actor, work_id, op)
    return {"event_id": event.id, "seq": event.seq}


@app.post("/works/{work_id}/events/{event_id}/undo")
async def undo_event(work_id: str, event_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    event = await gateway.undo(session, authz, actor, work_id, event_id)
    return {"event_id": event.id, "seq": event.seq}


@app.get("/works/{work_id}/events")
async def list_events(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep, after: int = 0,
                      limit: int = 200):
    await require(authz, actor, "can_view", work_obj(work_id))
    events = (
        await session.execute(
            select(Event).where(Event.work_id == work_id, Event.seq > after).order_by(Event.seq).limit(limit)
        )
    ).scalars().all()
    return [
        row(e, "id", "seq", "actor_kind", "actor_id", "on_behalf_of", "op_type", "payload", "undoes_event_id",
            "created_at") | {"undoable": e.inverse is not None}
        for e in events
    ]


# ---------------------------------------------------------------- ロック


class NewLock(BaseModel):
    target_kind: Literal["page", "panel", "item"]
    target_id: str
    reason: str
    page_id: str | None = None


@app.post("/works/{work_id}/locks", status_code=201)
async def acquire_lock(work_id: str, body: NewLock, session: SessionDep, authz: AuthzDep,
                       temporal: TemporalDep, actor: ActorDep):
    result = await locks.acquire(session, authz, actor, work_id, body.target_kind, body.target_id, body.reason,
                                 body.page_id)
    # 人が取り返したAIのロックの作業を止める（V3ハーネス設計 4.3）
    for job_id in result.preempted_job_ids:
        job = await session.get(Job, job_id)
        if job is not None and job.status not in ("done", "cancelled", "stopped"):
            await job_ops.cancel(temporal, job)
    return {"id": result.lock.id, "expires_at": result.lock.expires_at,
            "preempted_job_ids": result.preempted_job_ids}


@app.delete("/works/{work_id}/locks/{lock_id}", status_code=204)
async def release_lock(work_id: str, lock_id: str, session: SessionDep, actor: ActorDep):
    await locks.release(session, actor, work_id, lock_id)


@app.get("/works/{work_id}/locks")
async def list_locks(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    rows = (await session.execute(select(Lock).where(Lock.work_id == work_id))).scalars().all()
    return [row(lk, "id", "target_kind", "target_id", "page_id", "holder_kind", "holder_id", "reason", "job_id",
                "expires_at") for lk in rows]


# ---------------------------------------------------------------- 依頼（順番待ち）


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


@app.post("/works/{work_id}/jobs", status_code=201)
async def create_job(work_id: str, body: NewJob, session: SessionDep, authz: AuthzDep, temporal: TemporalDep,
                     actor: ActorDep):
    job = await job_ops.enqueue(session, authz, temporal, actor, work_id, body.process, body.request, "human",
                                body.page_id)
    return row(job, *JOB_FIELDS)


@app.get("/works/{work_id}/jobs")
async def list_jobs(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """進捗一覧の元。止まったもの・待っているものも出す。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    rows = (
        await session.execute(select(Job).where(Job.work_id == work_id).order_by(Job.created_at))
    ).scalars().all()
    return [row(j, *JOB_FIELDS) for j in rows]


@app.post("/works/{work_id}/jobs/{job_id}/cancel", status_code=202)
async def cancel_job(work_id: str, job_id: str, session: SessionDep, authz: AuthzDep, temporal: TemporalDep,
                     actor: ActorDep):
    job = await _job_in_work(session, work_id, job_id)
    if job.requested_by != actor.id:
        await require(authz, actor, "can_manage", work_obj(work_id))
    await job_ops.cancel(temporal, job)


@app.post("/works/{work_id}/jobs/{job_id}/resume", status_code=202)
async def resume_job(work_id: str, job_id: str, session: SessionDep, authz: AuthzDep, temporal: TemporalDep,
                     actor: ActorDep):
    await require(authz, actor, "can_manage", work_obj(work_id))
    await job_ops.resume(temporal, await _job_in_work(session, work_id, job_id))


@app.post("/works/{work_id}/jobs/{job_id}/retry", status_code=201)
async def retry_job(work_id: str, job_id: str, session: SessionDep, authz: AuthzDep, temporal: TemporalDep,
                    actor: ActorDep):
    """止まったものの「もう一度」。いまの処理ごとの送り先へ、同じ中身で新しく頼む。"""
    job = await _job_in_work(session, work_id, job_id)
    if job.status != "stopped":
        raise Invalid("止まったものだけもう一度頼める")
    new_job = await job_ops.enqueue(session, authz, temporal, actor, work_id, job.process, job.request, "human",
                                    job.page_id)
    return row(new_job, *JOB_FIELDS)


# ---------------------------------------------------------------- つなぎ先と処理ごとの送り先（全作品で共通）


class NewService(BaseModel):
    name: str
    kind: Literal["image", "text"]
    location: Literal["local", "api"]
    adapter: Literal["comfyui", "litellm"]
    endpoint: str | None = None
    send_mode: Literal["serial", "parallel"]
    max_concurrency: int = Field(default=1, ge=1)
    monthly_budget: float | None = None


class ServicePatch(BaseModel):
    endpoint: str | None = None
    send_mode: Literal["serial", "parallel"] | None = None
    max_concurrency: int | None = Field(default=None, ge=1)
    paused: bool | None = None
    monthly_budget: float | None = None
    state: Literal["connected", "stopped", "key_rejected", "unchecked"] | None = None


class ServiceProcessBody(BaseModel):
    aptitude: Literal["good", "normal", "poor"] | None = None
    cost_per_call: float | None = None
    model: str | None = None
    comfy_workflow: dict[str, Any] | None = None


class RouteBody(BaseModel):
    service_id: str
    resend_limit: int = Field(ge=0)
    regenerate_limit: int = Field(ge=0)


SERVICE_FIELDS = ("id", "name", "kind", "location", "adapter", "endpoint", "send_mode", "max_concurrency", "state",
                  "paused", "monthly_budget")


@app.get("/services")
async def list_services(session: SessionDep, actor: ActorDep):
    services = (await session.execute(select(Service).order_by(Service.name))).scalars().all()
    sps = (await session.execute(select(ServiceProcess))).scalars().all()
    routes = (await session.execute(select(ProcessRoute))).scalars().all()
    return {
        "services": [row(s, *SERVICE_FIELDS) for s in services],
        "processes": [row(sp, "service_id", "process", "aptitude", "cost_per_call", "model") for sp in sps],
        "routes": [row(r, "process", "service_id", "resend_limit", "regenerate_limit") for r in routes],
    }


@app.post("/services", status_code=201)
async def create_service(body: NewService, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "admin", SYSTEM_OBJ)
    service = Service(**body.model_dump())
    session.add(service)
    await session.commit()
    return row(service, *SERVICE_FIELDS)


@app.patch("/services/{service_id}")
async def patch_service(service_id: str, body: ServicePatch, session: SessionDep, authz: AuthzDep,
                        actor: ActorDep):
    """休ませる・戻す、送り方を変える。作業者は数秒で作り直される（queue/worker.py）。"""
    await require(authz, actor, "admin", SYSTEM_OBJ)
    service = await session.get(Service, service_id)
    if service is None:
        raise NotFound(f"services:{service_id}")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(service, k, v)
    await session.commit()
    return row(service, *SERVICE_FIELDS)


@app.put("/services/{service_id}/processes/{process}")
async def put_service_process(service_id: str, process: str, body: ServiceProcessBody, session: SessionDep,
                              authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "admin", SYSTEM_OBJ)
    if await session.get(Service, service_id) is None:
        raise NotFound(f"services:{service_id}")
    sp = (
        await session.execute(
            select(ServiceProcess).where(ServiceProcess.service_id == service_id, ServiceProcess.process == process)
        )
    ).scalar_one_or_none()
    if sp is None:
        sp = ServiceProcess(service_id=service_id, process=process)
        session.add(sp)
    for k, v in body.model_dump().items():
        setattr(sp, k, v)
    await session.commit()
    return row(sp, "service_id", "process", "aptitude", "cost_per_call", "model")


@app.put("/routes/{process}")
async def put_route(process: str, body: RouteBody, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """処理の送り先を1つ決める。その先がその処理を受けられないときは選べない。"""
    await require(authz, actor, "admin", SYSTEM_OBJ)
    sp = (
        await session.execute(
            select(ServiceProcess).where(ServiceProcess.service_id == body.service_id,
                                         ServiceProcess.process == process)
        )
    ).scalar_one_or_none()
    if sp is None:
        raise Invalid("そのつなぎ先はこの処理を受けられない（先に処理の中身を登録する）")
    route = await session.get(ProcessRoute, process)
    if route is None:
        route = ProcessRoute(process=process, **body.model_dump())
        session.add(route)
    else:
        for k, v in body.model_dump().items():
            setattr(route, k, v)
    await session.commit()
    return row(route, "process", "service_id", "resend_limit", "regenerate_limit")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "time": datetime.now().isoformat()}
