"""つなぎ先と処理ごとの送り先（全作品で共通）の口。"""


from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from v3server.allowed_destinations import effective_location, is_allowed, proves_local
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
from v3server.generation_queue.image_process_registry import SPECS, parse_settings
from v3server.generation_queue.known_processes import check_process_task
from v3server.operations.ai_involvement import Task
from v3server.operations.operation_base import work_obj
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
    # 画像生成の処理（generation_queue/image_process_registry.py）の中身。モデル名・サンプラーなど。処理の形で確かめる
    comfy_graph_settings: dict[str, Any] | None = None


class RouteBody(BaseModel):
    service_id: str
    resend_limit: int = Field(ge=0)
    regenerate_limit: int = Field(ge=0)
    # この処理が何の作業の、どの手か（operations/ai_involvement.py）。作る処理は propose、検査する処理は check
    ai_task: Task
    ai_action: Literal["propose", "check"]


SERVICE_FIELDS = ("id", "name", "kind", "location", "adapter", "endpoint", "send_mode", "max_concurrency", "state",
                  "paused", "monthly_budget", "usage_terms")
SP_FIELDS = ("service_id", "process", "aptitude", "cost_per_call", "model", "comfy_wait_seconds",
             "comfy_check_choices", "comfy_graph_settings")
ROUTE_FIELDS = ("process", "service_id", "resend_limit", "regenerate_limit", "ai_task", "ai_action")


def _require_local_proven(location: str, adapter: str, endpoint: str | None) -> None:
    """local と登録するなら、手元と言えること（allowed_destinations.proves_local）。言えなければ断る（api で登録する）。"""
    if location != "local":
        return
    ok, why = proves_local(adapter, endpoint)
    if not ok:
        raise Invalid(f"local と言えない（{why}）。api として登録し、作品ごとに送ってよい先へ載せる")


# 作品の参加者に見せる項目。住所（endpoint）・月の予算・処理ごとの費用と中身は、管理者だけが見る
MEMBER_SERVICE_FIELDS = ("id", "name", "kind", "state", "paused", "usage_terms")


@router.get("/works/{work_id}/services")
async def list_work_services(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """作品の参加者が見るつなぎ先：名前・種類・手元か・状態・利用規約の要点と、この作品から送ってよいか。
    処理ごとの送り先は、処理の名前と送り先の id だけ。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    services = (await session.execute(select(Service).order_by(Service.name))).scalars().all()
    routes = (await session.execute(select(ProcessRoute))).scalars().all()
    return {
        "services": [row(s, *MEMBER_SERVICE_FIELDS) | {"location": effective_location(s),
                                                        "allowed": await is_allowed(session, work_id, s)}
                     for s in services],
        "routes": [row(r, "process", "service_id") for r in routes],
    }


@router.get("/services")
async def list_services(session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """つなぎ先の全部（住所・予算・費用・中身を含む）。管理者だけ。作品の参加者は /works/{id}/services。"""
    await require(authz, actor, "admin", SYSTEM_OBJ)
    services = (await session.execute(select(Service).order_by(Service.name))).scalars().all()
    sps = (await session.execute(select(ServiceProcess))).scalars().all()
    routes = (await session.execute(select(ProcessRoute))).scalars().all()
    return {
        "services": [row(s, *SERVICE_FIELDS) for s in services],
        "processes": [row(sp, *SP_FIELDS) for sp in sps],
        "routes": [row(r, *ROUTE_FIELDS) for r in routes],
    }


@router.post("/services", status_code=201)
async def create_service(body: NewService, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "admin", SYSTEM_OBJ)
    _require_local_proven(body.location, body.adapter, body.endpoint)
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
    _require_local_proven(service.location, service.adapter, service.endpoint)
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
    if body.comfy_graph_settings is not None:
        if process not in SPECS:
            raise Invalid(f"comfy_graph_settings は画像生成の処理（{', '.join(SPECS)}）だけに入れる")
        parse_settings(SPECS[process], body.comfy_graph_settings)
    for k, v in body.model_dump().items():
        setattr(sp, k, v)
    await session.commit()
    return row(sp, *SP_FIELDS)


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
