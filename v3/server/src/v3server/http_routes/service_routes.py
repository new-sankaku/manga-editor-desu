"""つなぎ先と処理ごとの送り先（全作品で共通）の口。"""


from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from v3server.canonical_tables.service_and_job_tables import (
    ProcessRoute,
    Service,
    ServiceProcess,
)
from v3server.http_routes.http_dependencies import (
    SYSTEM_OBJ,
    ActorDep,
    AuthzDep,
    SessionDep,
    require,
    row,
)
from v3server.generation_queue.known_processes import check_process_task
from v3server.operations.ai_involvement import Task
from v3server.usage_terms_schema import UsageTerms
from v3server.v3_error_types import Invalid, NotFound

# ---------------------------------------------------------------- つなぎ先と処理ごとの送り先（全作品で共通）

router = APIRouter()


class NewService(BaseModel):
    name: str
    kind: Literal["image", "text"]
    location: Literal["local", "api"]
    adapter: Literal["comfyui", "litellm", "detector"]
    endpoint: str | None = None
    send_mode: Literal["serial", "parallel"]
    max_concurrency: int = Field(default=1, ge=1)
    monthly_budget: float | None = None
    # 利用規約の要点（V3細部の決めごと 20章）。人が確かめて入れる。無ければ未記録
    usage_terms: UsageTerms | None = None


class ServicePatch(BaseModel):
    endpoint: str | None = None
    send_mode: Literal["serial", "parallel"] | None = None
    max_concurrency: int | None = Field(default=None, ge=1)
    paused: bool | None = None
    monthly_budget: float | None = None
    state: Literal["connected", "stopped", "key_rejected", "unchecked"] | None = None
    usage_terms: UsageTerms | None = None


class ServiceProcessBody(BaseModel):
    aptitude: Literal["good", "normal", "poor"] | None = None
    cost_per_call: float | None = None
    model: str | None = None
    comfy_workflow: dict[str, Any] | None = None
    comfy_wait_seconds: int | None = Field(default=None, ge=1)
    comfy_check_choices: bool = False


class RouteBody(BaseModel):
    service_id: str
    resend_limit: int = Field(ge=0)
    regenerate_limit: int = Field(ge=0)
    # この処理が何の作業の、どの手か（operations/ai_involvement.py）。作る処理は propose、検査する処理は check
    ai_task: Task
    ai_action: Literal["propose", "check"]


SERVICE_FIELDS = ("id", "name", "kind", "location", "adapter", "endpoint", "send_mode", "max_concurrency", "state",
                  "paused", "monthly_budget", "usage_terms")
ROUTE_FIELDS = ("process", "service_id", "resend_limit", "regenerate_limit", "ai_task", "ai_action")


@router.get("/services")
async def list_services(session: SessionDep, actor: ActorDep):
    services = (await session.execute(select(Service).order_by(Service.name))).scalars().all()
    sps = (await session.execute(select(ServiceProcess))).scalars().all()
    routes = (await session.execute(select(ProcessRoute))).scalars().all()
    return {
        "services": [row(s, *SERVICE_FIELDS) for s in services],
        "processes": [row(sp, "service_id", "process", "aptitude", "cost_per_call", "model",
                                        "comfy_wait_seconds", "comfy_check_choices") for sp in sps],
        "routes": [row(r, *ROUTE_FIELDS) for r in routes],
    }


@router.post("/services", status_code=201)
async def create_service(body: NewService, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "admin", SYSTEM_OBJ)
    service = Service(**body.model_dump(mode="json"))
    session.add(service)
    await session.commit()
    return row(service, *SERVICE_FIELDS)


@router.patch("/services/{service_id}")
async def patch_service(service_id: str, body: ServicePatch, session: SessionDep, authz: AuthzDep,
                        actor: ActorDep):
    """休ませる・戻す、送り方を変える。作業者は数秒で作り直される（generation_queue/queue_worker_main.py）。"""
    await require(authz, actor, "admin", SYSTEM_OBJ)
    service = await session.get(Service, service_id)
    if service is None:
        raise NotFound(f"services:{service_id}")
    for k, v in body.model_dump(exclude_unset=True, mode="json").items():
        setattr(service, k, v)
    await session.commit()
    return row(service, *SERVICE_FIELDS)


@router.put("/services/{service_id}/processes/{process}")
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
    return row(sp, "service_id", "process", "aptitude", "cost_per_call", "model",
                                        "comfy_wait_seconds", "comfy_check_choices")


@router.put("/routes/{process}")
async def put_route(process: str, body: RouteBody, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """処理の送り先を1つ決める。その先がその処理を受けられないときは選べない。"""
    await require(authz, actor, "admin", SYSTEM_OBJ)
    check_process_task(process, body.ai_task, body.ai_action)
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
    return row(route, *ROUTE_FIELDS)
