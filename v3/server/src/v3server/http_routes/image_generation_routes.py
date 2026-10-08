"""画像生成の画面（v3/web/）の口。処理の一覧・頼む・候補・版・縮めた絵。説明は llm_doc/V3画像生成の機能と画面.md。

採る・却下する・前の版に戻すは操作の窓口（POST /works/{id}/ops の adopt_image・set_image_discarded）を通す。取り消しも同じ。
進み具合は画面が数秒ごとに見に来る（GET /works/{id}/panels/{id}/candidates）。SSE にしない理由：ブラウザの EventSource は
見出し（X-V3-User）を付けられない。状態は作業者が PostgreSQL に書くので、見に来た時に読めば足りる。
"""
from __future__ import annotations

import io
import secrets
from typing import Any, Literal

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field
from PIL import Image
from sqlalchemy import select

from v3server.canonical_tables.event_and_lock_tables import Event
from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.service_and_job_tables import Job, ProcessRoute, Service, ServiceProcess
from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.work_tree_tables import Panel, Work
from v3server.allowed_destinations import is_allowed
from v3server.generation_queue import job_start_and_control
from v3server.comfy_graphs.protected_region_mask import protected_mask_png
from v3server.generation_queue.image_process_preparation import SEED_MAX
from v3server.generation_queue.input_image_preparation import protected_regions_for
from v3server.generation_queue.image_process_registry import SPECS, describe, resolve_outpaint, spec_for
from v3server.http_routes.http_dependencies import ActorDep, AuthzDep, SessionDep, TemporalDep, require, row
from v3server.http_routes.image_file_routes import IMAGE_FIELDS
from v3server.http_routes.job_routes import JOB_FIELDS
from v3server.image_file_storage import read_image
from v3server.operations.image_placement_carry import frame_bbox
from v3server.operations.operation_base import get_in_work, work_obj
from v3server.v3_error_types import Invalid, NotFound

router = APIRouter()

# 一度に頼める候補の数（画面の 2・4・6 案と、送り先の順番待ちを詰まらせない上限）
MAX_COUNT = 8
# 「固定」のときの種の上限。乱数のときもこの範囲で選ぶ（ComfyUI の KSampler の seed に入る範囲の内）
RANDOM_SEED_LIMIT = 2**32


def settings_summary(settings: dict[str, Any] | None) -> dict[str, Any] | None:
    """つなぎ先の中身から、画面に出す要点（モデル・追加学習・得意な大きさ・形の指定を使えるか）。"""
    if not settings:
        return None
    m = settings.get("model") or {}
    model = m.get("checkpoint_name") or m.get("unet_name") or settings.get("unet_name")
    return {"model": model, "loras": [x.get("name") for x in settings.get("loras", [])],
            "native_long_side": settings.get("native_long_side"),
            "controlnet": settings.get("controlnet_name") is not None,
            "resolution": settings.get("resolution")}


@router.get("/works")
async def list_works(session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """見てよい作品の一覧（画面で作品を選ぶ）。"""
    works = (await session.execute(select(Work).order_by(Work.title))).scalars().all()
    return [{"id": w.id, "title": w.title} for w in works
            if await authz.check(actor.permission_user, "can_view", work_obj(w.id))]


@router.get("/works/{work_id}/image-processes")
async def list_image_processes(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """画像生成の処理ごとの説明・入力欄の形・送り先・選べるつなぎ先。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    sps = (await session.execute(select(ServiceProcess).where(ServiceProcess.process.in_(list(SPECS))))).scalars().all()
    services = {s.id: s for s in (await session.execute(select(Service))).scalars().all()}
    out = []
    for spec in SPECS.values():
        route = await session.get(ProcessRoute, spec.name)
        choices = []
        for sp in sps:
            if sp.process != spec.name:
                continue
            svc = services[sp.service_id]
            choices.append({"service_id": svc.id, "name": svc.name, "location": svc.location, "state": svc.state,
                            "paused": svc.paused, "allowed": await is_allowed(session, work_id, svc),
                            "settings": settings_summary(sp.comfy_graph_settings)})
        out.append({**describe(spec), "route_service_id": route.service_id if route else None, "services": choices})
    return out


class MaskInput(BaseModel):
    png_base64: str | None = None
    region_px: list[list[list[float]]] | None = None


class ControlInput(BaseModel):
    png_base64: str | None = None
    image_id: str | None = None


class GenerateBody(BaseModel):
    process: str
    params: dict[str, Any]
    count: int = Field(ge=1, le=MAX_COUNT)
    seed_mode: Literal["random", "fixed"]
    seed: int | None = Field(default=None, ge=0, le=SEED_MAX)
    # 元の絵。文から作るでは渡さない
    source_image_id: str | None = None
    mask: MaskInput | None = None
    control: ControlInput | None = None
    # 送り先を変えるとき（無ければ処理の送り先）
    service_id: str | None = None


def _one_of(value: BaseModel, what: str) -> dict[str, Any]:
    given = {k: v for k, v in value.model_dump().items() if v is not None}
    if len(given) != 1:
        raise Invalid(f"{what} は {', '.join(type(value).model_fields)} のどれか1つで渡す")
    return given


@router.post("/works/{work_id}/panels/{panel_id}/generate", status_code=201)
async def generate(work_id: str, panel_id: str, body: GenerateBody, session: SessionDep, authz: AuthzDep,
                   temporal: TemporalDep, actor: ActorDep):
    """候補を count 枚頼む（1枚ずつ別の依頼。種は1枚ごとに違う）。同じ candidate_set_id でまとまる。"""
    panel = await get_in_work(session, Panel, panel_id, work_id)
    spec = spec_for(body.process)
    if body.seed_mode == "fixed" and body.seed is None:
        raise Invalid("種を固定するときは seed を渡す")
    if body.seed_mode == "random" and body.seed is not None:
        raise Invalid("種を乱数にするときは seed を渡さない")
    params = body.params
    inputs: list[dict[str, Any]] = []
    if spec.source == "required":
        if body.source_image_id is None:
            raise Invalid(f"{spec.label} は元の絵（source_image_id）が要る")
        src = await get_in_work(session, ImageFile, body.source_image_id, work_id)
        inputs.append({"node": "source", "input": "image", "image_id": src.id, "purpose": "source"})
        if spec.name == "outpaint":
            placement = panel.image_placement if panel.image_id == src.id else None
            params = resolve_outpaint(params, placement, frame_bbox(panel.frame), (src.width, src.height))
    elif body.source_image_id is not None:
        raise Invalid(f"{spec.label} は元の絵を受けない")
    if body.mask is not None:
        inputs.append({"node": "redraw_mask", "input": "image", "purpose": "mask", **_one_of(body.mask, "mask")})
    if body.control is not None:
        inputs.append({"node": "control", "input": "image", "purpose": "control",
                       **_one_of(body.control, "control")})
    set_id = new_id()
    seeds = ([body.seed + i for i in range(body.count)] if body.seed_mode == "fixed"
             else [secrets.randbelow(RANDOM_SEED_LIMIT) for _ in range(body.count)])
    if max(seeds) > SEED_MAX:
        raise Invalid("種が上限を超える")
    jobs = []
    for seed in seeds:
        request: dict[str, Any] = {
            "image_process": {"name": spec.name, "params": params, "seed": seed, "candidate_set_id": set_id,
                              "requested_params": body.params},
            "register": {"role": "panel_art", "page_id": panel.page_id, "panel_id": panel.id},
        }
        if inputs:
            request["input_images"] = inputs
        if spec.source == "required":
            request["protected_mask_input"] = {"node": "protected_mask", "input": "image"}
        job = await job_start_and_control.enqueue(session, authz, temporal, actor, work_id, spec.name, request,
                                                  "human", panel.page_id, body.service_id)
        jobs.append(row(job, *JOB_FIELDS))
    return {"candidate_set_id": set_id, "jobs": jobs}


def _protected_entry(job: Job) -> dict[str, Any] | None:
    for e in job.request.get("prepared_inputs", []):
        if e.get("purpose") == "protected_mask":
            return e
    return None


def _job_brief(work_id: str, job: Job) -> dict[str, Any]:
    ip = job.request["image_process"]
    prot = _protected_entry(job)
    return {"id": job.id, "status": job.status, "failure_kind": job.failure_kind, "failure_detail": job.failure_detail,
            "service_id": job.service_id, "seed": ip["seed"], "created_at": job.created_at,
            "protected_mask_url": (f"/works/{work_id}/jobs/{job.id}/protected-mask"
                                   if prot is not None and prot.get("region_ids") else None)}


@router.get("/works/{work_id}/panels/{panel_id}/candidates")
async def list_candidates(work_id: str, panel_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """このコマに頼んだ画像生成の候補を、頼んだまとまりごとに新しい順で。進み具合もここで見る。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    panel = await get_in_work(session, Panel, panel_id, work_id)
    jobs = [j for j in (await session.execute(
        select(Job).where(Job.work_id == work_id, Job.page_id == panel.page_id).order_by(Job.created_at.desc())
    )).scalars().all() if "image_process" in j.request and j.request.get("register", {}).get("panel_id") == panel_id]
    images = (await session.execute(select(ImageFile).where(ImageFile.job_id.in_([j.id for j in jobs])))).scalars().all() \
        if jobs else []
    services = {s.id: s for s in (await session.execute(select(Service))).scalars().all()}
    sps = {(sp.service_id, sp.process): sp for sp in (await session.execute(
        select(ServiceProcess).where(ServiceProcess.process.in_(list(SPECS))))).scalars().all()}
    sets: dict[str, dict[str, Any]] = {}
    for j in jobs:
        ip = j.request["image_process"]
        s = sets.setdefault(ip["candidate_set_id"], {
            "candidate_set_id": ip["candidate_set_id"], "process": ip["name"], "label": SPECS[ip["name"]].label,
            "requested_params": ip.get("requested_params"), "params": ip["params"],
            "source_image_id": next((e.get("image_id") for e in j.request.get("prepared_inputs", [])
                                     if e.get("purpose") == "source"), None),
            "created_at": j.created_at, "jobs": [], "images": []})
        brief = _job_brief(work_id, j)
        svc = services.get(j.service_id)
        sp = sps.get((j.service_id, j.process))
        brief["service_name"] = svc.name if svc else None
        brief["settings"] = settings_summary(sp.comfy_graph_settings) if sp else None
        s["jobs"].append(brief)
        for img in images:
            if img.job_id == j.id:
                s["images"].append({**row(img, *IMAGE_FIELDS), "job_id": j.id, "seed": ip["seed"],
                                    "service_name": brief["service_name"], "settings": brief["settings"],
                                    "protected_mask_url": brief["protected_mask_url"]})
    return {"panel_image_id": panel.image_id, "sets": list(sets.values())}


@router.get("/works/{work_id}/jobs/{job_id}/protected-mask")
async def get_protected_mask(work_id: str, job_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """その依頼で描き直さなかった人の手の範囲（白）。出来上がりの絵と同じ大きさ（描き足すでは広げた後の位置）。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    job = await session.get(Job, job_id)
    if job is None or job.work_id != work_id:
        raise NotFound(f"jobs:{job_id}")
    prot = _protected_entry(job)
    if prot is None:
        raise NotFound(f"jobs:{job_id} に人の手の範囲のマスクが無い")
    return Response(read_image(prot["sha256"]), media_type=prot["media_type"])


@router.get("/works/{work_id}/panels/{panel_id}/versions")
async def list_versions(work_id: str, panel_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """このコマの絵の版（based_on の鎖）。却下した候補は除く。今の絵と、その祖先（別のコマの絵でも）を含む。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    panel = await get_in_work(session, Panel, panel_id, work_id)
    imgs = {i.id: i for i in (await session.execute(
        select(ImageFile).where(ImageFile.work_id == work_id, ImageFile.panel_id == panel_id,
                                ImageFile.discarded.is_(False)))).scalars().all()}
    cur = await session.get(ImageFile, panel.image_id) if panel.image_id else None
    while cur is not None and len(imgs) < 10_000:
        imgs.setdefault(cur.id, cur)
        cur = await session.get(ImageFile, cur.based_on_image_id) if cur.based_on_image_id else None
    # 候補のうち採っていない物は、版の一覧には出さない（候補の一覧で見る）。人の絵と、採った物の祖先は出す
    ancestors = set()
    cur_id = panel.image_id
    while cur_id is not None and cur_id in imgs and cur_id not in ancestors:
        ancestors.add(cur_id)
        cur_id = imgs[cur_id].based_on_image_id
    adopted = await _adopted_ids(session, work_id, panel_id)
    shown = [i for i in imgs.values() if i.origin != "generated" or i.id in ancestors or i.id in adopted]
    shown.sort(key=lambda i: i.created_at)
    return {"panel_image_id": panel.image_id,
            "versions": [{**row(i, *IMAGE_FIELDS), "current": i.id == panel.image_id} for i in shown]}


async def _adopted_ids(session, work_id: str, panel_id: str) -> set[str]:
    """このコマに一度でも採った絵（操作の記録の adopt_image）。"""
    rows = (await session.execute(select(Event.payload).where(Event.work_id == work_id,
                                                              Event.op_type == "adopt_image"))).scalars().all()
    return {p["image_id"] for p in rows if p.get("panel_id") == panel_id}


@router.get("/works/{work_id}/images/{image_id}/thumbnail")
async def get_thumbnail(work_id: str, image_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep,
                        size: int = Query(ge=32, le=1024)):
    """長い辺を size にした絵（候補の一覧・版の一覧）。中身は変わらないので、ブラウザに長く持たせる。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    img = await get_in_work(session, ImageFile, image_id, work_id)
    with Image.open(io.BytesIO(read_image(img.sha256))) as im:
        im = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
        im.thumbnail((size, size), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png",
                    headers={"Cache-Control": "private, max-age=31536000, immutable"})


@router.get("/works/{work_id}/images/{image_id}/protected-mask")
async def get_image_protected_mask(work_id: str, image_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """この絵を元に頼んだときに描き直さない人の手の範囲（白）。画面で囲めない所として見せる。
    依頼を受けるとき（input_image_preparation.py）と同じ範囲・同じ描き方。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    img = await get_in_work(session, ImageFile, image_id, work_id)
    regions = await protected_regions_for(session, img)
    data = protected_mask_png(img.width, img.height, [r.polygon_px for r in regions if r.polygon_px is not None],
                              [read_image(r.mask_sha256) for r in regions if r.mask_sha256])
    return Response(data, media_type="image/png", headers={"X-V3-Region-Count": str(len(regions))})
