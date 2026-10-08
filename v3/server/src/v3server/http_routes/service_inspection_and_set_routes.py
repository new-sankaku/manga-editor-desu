"""生成サービスの画面の口のうち、つなぎ先の様子を読む口と、組・比べ。

- POST /services/{id}/connection-test：つながるかを試し、結果を Service.state に入れる（connected・stopped・key_rejected）
- GET  /services/{id}/status：つなぎ先の側で走っている・待っている数（ComfyUI の /queue）と、このつなぎ先への依頼の
  状態ごとの数と、止まった依頼（status=stopped。新しい順に 50 件）
- GET  /services/{id}/models：入っているモデル（ComfyUI の /object_info と /system_stats、LiteLLM の /v1/models）
- GET・POST /service-sets、PUT・DELETE /service-sets/{id}：管理者が作った組（処理ごとの送り先の並び）を残す
- POST /service-sets/{id}/apply：組を当てる。送り先が決まっている処理だけ、送り先のつなぎ先を替える（送り直しの回数・作業と手は
  今の送り先のまま）。送り先がまだ無い処理は、回数を決められないので断る（先に PUT /routes/{process}）。1回の確定で全部当てる
- POST /works/{id}/service-comparisons：同じ指示を、いくつものつなぎ先へ1件ずつ頼む（job_start_and_control.enqueue の
  service_id。送ってよい先の決まりと作業のAIの関与は、1件ずつに同じにかかる）。GET で、頼んだ依頼の状態と結果を並べて返す
どれも管理者（system:main の admin）だけ。比べるのは作品の中の依頼なので、依頼を出せる人（enqueue が確かめる）。
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from v3server.canonical_tables.service_and_job_tables import Job, ProcessRoute, Service, ServiceProcess
from v3server.canonical_tables.service_set_and_preview_tables import ServiceComparison, ServiceSet
from v3server.generation_queue import job_start_and_control
from v3server.http_routes.http_dependencies import (
    SYSTEM_OBJ,
    ActorDep,
    AuthzDep,
    SessionDep,
    TemporalDep,
    require,
    row,
)
from v3server.http_routes.job_routes import JOB_FIELDS
from v3server.operations.operation_base import get_in_work, work_obj
from v3server.service_senders.service_inspection import (
    InspectionError,
    connection_test,
    installed_models,
    running_state,
)
from v3server.v3_error_types import Invalid, NotFound

router = APIRouter()


async def _service(session, service_id: str) -> Service:
    service = await session.get(Service, service_id)
    if service is None:
        raise NotFound(f"services:{service_id}")
    return service


@router.post("/services/{service_id}/connection-test")
async def test_connection(service_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "admin", SYSTEM_OBJ)
    service = await _service(session, service_id)
    try:
        result = await connection_test(service)
    except InspectionError as e:
        service.state = e.state
        await session.commit()
        return {"ok": False, "state": e.state, "detail": e.detail}
    service.state = "connected"
    await session.commit()
    return {"ok": True, "state": "connected", "result": result}


@router.get("/services/{service_id}/status")
async def service_status(service_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "admin", SYSTEM_OBJ)
    service = await _service(session, service_id)
    try:
        remote: dict[str, Any] = {"ok": True, **await running_state(service)}
    except InspectionError as e:
        remote = {"ok": False, "state": e.state, "detail": e.detail}
    counts = dict((await session.execute(select(Job.status, func.count()).where(Job.service_id == service_id)
                                         .group_by(Job.status))).all())
    stopped = (await session.execute(select(Job).where(Job.service_id == service_id, Job.status == "stopped")
                                     .order_by(Job.updated_at.desc()).limit(50))).scalars().all()
    return {"service_id": service.id, "state": service.state, "paused": service.paused, "remote": remote,
            "job_counts": counts,
            "stopped_jobs": [row(j, "id", "work_id", "process", "failure_kind", "failure_detail", "updated_at")
                             for j in stopped]}


@router.get("/services/{service_id}/models")
async def service_models(service_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "admin", SYSTEM_OBJ)
    service = await _service(session, service_id)
    try:
        return {"ok": True, **await installed_models(service)}
    except InspectionError as e:
        return {"ok": False, "state": e.state, "detail": e.detail}


# ---------------------------------------------------------------- 組


class ServiceSetBody(BaseModel):
    name: str = Field(min_length=1)
    # {処理の名前: つなぎ先の id}
    routes: dict[str, str] = Field(min_length=1)


SET_FIELDS = ("id", "name", "routes", "created_by", "created_at", "updated_at")


async def _check_set_routes(session, routes: dict[str, str]) -> None:
    for process, service_id in routes.items():
        if await session.scalar(select(ServiceProcess.id).where(
                ServiceProcess.service_id == service_id, ServiceProcess.process == process)) is None:
            raise Invalid(f"つなぎ先 {service_id} は {process} を受けられない（先に処理の中身を登録する）")


@router.get("/service-sets")
async def list_service_sets(session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "admin", SYSTEM_OBJ)
    return [row(s, *SET_FIELDS) for s in (await session.execute(select(ServiceSet).order_by(ServiceSet.name))).scalars()]


@router.post("/service-sets", status_code=201)
async def create_service_set(body: ServiceSetBody, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "admin", SYSTEM_OBJ)
    if await session.scalar(select(ServiceSet.id).where(ServiceSet.name == body.name)) is not None:
        raise Invalid(f"組 {body.name} はもうある")
    await _check_set_routes(session, body.routes)
    s = ServiceSet(name=body.name, routes=body.routes, created_by=actor.id)
    session.add(s)
    await session.commit()
    await session.refresh(s)
    return row(s, *SET_FIELDS)


@router.put("/service-sets/{set_id}")
async def update_service_set(set_id: str, body: ServiceSetBody, session: SessionDep, authz: AuthzDep,
                             actor: ActorDep):
    await require(authz, actor, "admin", SYSTEM_OBJ)
    s = await session.get(ServiceSet, set_id)
    if s is None:
        raise NotFound(f"service_sets:{set_id}")
    if await session.scalar(select(ServiceSet.id).where(ServiceSet.name == body.name, ServiceSet.id != set_id)):
        raise Invalid(f"組 {body.name} はもうある")
    await _check_set_routes(session, body.routes)
    s.name, s.routes = body.name, body.routes
    await session.commit()
    await session.refresh(s)
    return row(s, *SET_FIELDS)


@router.delete("/service-sets/{set_id}", status_code=204)
async def delete_service_set(set_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "admin", SYSTEM_OBJ)
    s = await session.get(ServiceSet, set_id)
    if s is None:
        raise NotFound(f"service_sets:{set_id}")
    await session.delete(s)
    await session.commit()


@router.post("/service-sets/{set_id}/apply")
async def apply_service_set(set_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "admin", SYSTEM_OBJ)
    s = await session.get(ServiceSet, set_id)
    if s is None:
        raise NotFound(f"service_sets:{set_id}")
    await _check_set_routes(session, s.routes)
    routes = {r.process: r for r in (await session.execute(
        select(ProcessRoute).where(ProcessRoute.process.in_(list(s.routes))))).scalars()}
    missing = sorted(set(s.routes) - set(routes))
    if missing:
        raise Invalid(f"送り先がまだ無い処理がある（先に PUT /routes/{{process}} で決める）: {', '.join(missing)}")
    changed = []
    for process, service_id in sorted(s.routes.items()):
        if routes[process].service_id != service_id:
            changed.append({"process": process, "from": routes[process].service_id, "to": service_id})
            routes[process].service_id = service_id
    await session.commit()
    return {"set_id": s.id, "changed": changed}


# ---------------------------------------------------------------- 比べる


class ComparisonBody(BaseModel):
    process: str
    request: dict[str, Any]
    service_ids: list[str] = Field(min_length=2)
    page_id: str | None = None


COMPARISON_FIELDS = ("id", "work_id", "process", "page_id", "request", "jobs", "requested_by", "created_at")


@router.post("/works/{work_id}/service-comparisons", status_code=201)
async def compare_services(work_id: str, body: ComparisonBody, session: SessionDep, authz: AuthzDep,
                           temporal: TemporalDep, actor: ActorDep):
    """同じ指示を、選んだつなぎ先へ1件ずつ頼む。1件でも断られたら、そこで止めて理由を返す（頼み終えた依頼は残る）。"""
    if len(set(body.service_ids)) != len(body.service_ids):
        raise Invalid("同じつなぎ先が2回ある")
    jobs = []
    for sid in body.service_ids:
        job = await job_start_and_control.enqueue(session, authz, temporal, actor, work_id, body.process, body.request,
                                                  "human", body.page_id, service_id=sid)
        jobs.append({"service_id": sid, "job_id": job.id})
    c = ServiceComparison(work_id=work_id, process=body.process, page_id=body.page_id, request=body.request,
                          jobs=jobs, requested_by=actor.permission_user)
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return row(c, *COMPARISON_FIELDS)


@router.get("/works/{work_id}/service-comparisons")
async def list_comparisons(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    rows = (await session.execute(select(ServiceComparison).where(ServiceComparison.work_id == work_id)
                                  .order_by(ServiceComparison.created_at.desc()))).scalars().all()
    return [row(c, *COMPARISON_FIELDS) for c in rows]


@router.get("/works/{work_id}/service-comparisons/{comparison_id}")
async def get_comparison(work_id: str, comparison_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    c = await get_in_work(session, ServiceComparison, comparison_id, work_id)
    out = row(c, *COMPARISON_FIELDS)
    out["results"] = [row(await session.get(Job, j["job_id"]), *JOB_FIELDS) for j in c.jobs]
    return out
