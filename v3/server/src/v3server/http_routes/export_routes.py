"""書き出しの口（V3細部の決めごと 10.4 の書き出し）と、人が直した PSD を戻す口。

- POST /works/{id}/exports：書き出しの依頼（ExportRun）を作り、書き出しの待ち行列に入れる（print_export/export_workflow.py）
  - 権限：PNG・PDF は作品を見られる人、PSD は書き出すページをどれも描ける人（PSD は直して戻すための書き出し）
  - 解像度（dpi）は必ず渡す。紙の大きさ（paper_mm）は任意（無ければ塗り足し込みのページの大きさ）
- GET /works/{id}/exports/{run_id}：状態と出力の一覧。PSD はペンの線が画素になることを note で返す（画面に出す文）
- GET /works/{id}/exports/{run_id}/files/{name}：書き出したファイル
- POST /works/{id}/exports/{run_id}/pages/{page_id}/psd：直した PSD を戻す（operations/psd_import_operations.py）
"""

import io
import pathlib
from typing import Annotated, Literal

import numpy as np
from PIL import Image
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from temporalio.common import Priority

from v3server.canonical_tables.material_and_setting_tables import ExportRun
from v3server.canonical_tables.text_and_layer_tables import HeldAiChange
from v3server.canonical_tables.work_tree_tables import Page, Work
from v3server.http_routes.http_dependencies import ActorDep, AuthzDep, SessionDep, TemporalDep, require, row
from v3server.image_file_storage import read_image
from v3server.image_intake import take_in_image
from v3server.name_structure.reading_direction import PageSpec
from v3server.operations import operation_submit_and_undo
from v3server.operations.operation_base import get_in_work, page_obj, work_obj
from v3server.operations.pen_stroke_operations import StoredResult
from v3server.operations.psd_import_operations import ApplyPsdImport, PsdImportEntry
from v3server.print_export.export_runner import PSD_STROKE_NOTE
from v3server.print_export.export_workflow import EXPORT_QUEUE, ExportRunWorkflow
from v3server.print_export.page_render import mm_to_px_matrix
from v3server.print_export.psd_import_matching import ExportedLayer, import_actions, match_layers, read_psd
from v3server.server_settings import get_settings
from v3server.v3_error_types import Invalid, NotFound

router = APIRouter()

RUN_FIELDS = ("id", "work_id", "requested_by", "format", "page_ids", "dpi", "paper_mm", "status", "detail", "outputs",
              "created_at", "updated_at")


class ExportRequest(BaseModel):
    format: Literal["png", "pdf", "psd"]
    page_ids: list[str] = Field(min_length=1)
    dpi: int = Field(gt=0, le=2400)
    paper_mm: tuple[float, float] | None = None


async def _require_export(session, authz, actor, work_id: str, fmt: str, page_ids: list[str]) -> None:
    if fmt != "psd":
        await require(authz, actor, "can_view", work_obj(work_id))
        return
    for pid in page_ids:
        await require(authz, actor, "can_draw", page_obj(pid))


@router.post("/works/{work_id}/exports", status_code=201)
async def start_export(work_id: str, req: ExportRequest, session: SessionDep, authz: AuthzDep, actor: ActorDep,
                       temporal: TemporalDep):
    if await session.get(Work, work_id) is None:
        raise NotFound(f"作品 {work_id}")
    if len(set(req.page_ids)) != len(req.page_ids):
        raise Invalid("同じページが2回ある")
    for pid in req.page_ids:
        page = await get_in_work(session, Page, pid, work_id)
        if page.removed:
            raise Invalid(f"ページ {pid} は抜かれている")
    await _require_export(session, authz, actor, work_id, req.format, req.page_ids)
    run = ExportRun(work_id=work_id, requested_by=actor.id, format=req.format, page_ids=req.page_ids, dpi=req.dpi,
                    paper_mm=list(req.paper_mm) if req.paper_mm else None, status="queued", outputs=[])
    session.add(run)
    await session.flush()
    run.workflow_id = f"export-{run.id}"
    await session.commit()
    await session.refresh(run)
    await temporal.start_workflow(ExportRunWorkflow.run, run.id, id=run.workflow_id, task_queue=EXPORT_QUEUE,
                                  priority=Priority(priority_key=1, fairness_key=work_id))
    out = row(run, *RUN_FIELDS)
    if req.format == "psd":
        out["note"] = PSD_STROKE_NOTE
    return out


@router.get("/works/{work_id}/exports/{run_id}")
async def get_export(work_id: str, run_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    run = await get_in_work(session, ExportRun, run_id, work_id)
    await _require_export(session, authz, actor, work_id, run.format, run.page_ids)
    out = row(run, *RUN_FIELDS)
    if run.format == "psd":
        out["note"] = PSD_STROKE_NOTE
    return out


@router.get("/works/{work_id}/exports/{run_id}/files/{name}")
async def get_export_file(work_id: str, run_id: str, name: str, session: SessionDep, authz: AuthzDep,
                          actor: ActorDep):
    run = await get_in_work(session, ExportRun, run_id, work_id)
    await _require_export(session, authz, actor, work_id, run.format, run.page_ids)
    if run.status != "done" or name not in {o["file"] for o in run.outputs}:
        raise NotFound(f"書き出したファイル {name}")
    return FileResponse(pathlib.Path(get_settings().export_dir) / run.id / name, filename=name)


@router.post("/works/{work_id}/exports/{run_id}/pages/{page_id}/psd")
async def import_psd(work_id: str, run_id: str, page_id: str, psd: Annotated[UploadFile, File()],
                     session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """直した PSD を戻す。結び付けは print_export/psd_import_matching.py、当て方は ApplyPsdImport。"""
    await require(authz, actor, "can_draw", page_obj(page_id))
    run = await get_in_work(session, ExportRun, run_id, work_id)
    work = await session.get(Work, work_id)
    out = next((o for o in run.outputs if o.get("page_id") == page_id), None)
    if run.format != "psd" or run.status != "done" or out is None:
        raise Invalid("このページを PSD に書き出し終えた記録ではない")
    exported = {la["marker"]: ExportedLayer(la["marker"], la["table"], la["left"], la["top"],
                                            Image.open(io.BytesIO(read_image(la["sha256"]))).convert("RGBA"))
                for la in out["layers"]}
    read = read_psd(await psd.read())
    matches = match_layers(read, exported)
    inv = np.linalg.inv(mm_to_px_matrix(PageSpec.model_validate(work.page_spec), run.dpi))
    ox, oy = out["offset_px"]

    def px_to_mm(x, y):
        v = inv @ np.array([x - ox, y - oy, 1.0])
        return float(v[0]), float(v[1])

    entries = []
    for a in import_actions(matches, px_to_mm):
        image = None
        if a.image is not None:
            buf = io.BytesIO()
            a.image.save(buf, format="PNG")
            stored = await take_in_image(session, work_id, buf.getvalue(), "human_upload")
            image = StoredResult(sha256=stored.sha256, media_type=stored.media_type, width=stored.width,
                                 height=stored.height)
        entries.append(PsdImportEntry(kind=a.kind, marker=a.marker, table=a.table, image=image, box_mm=a.box_mm,
                                      parent_marker=a.parent_marker, layer_name=a.layer_name))
    event = await operation_submit_and_undo.submit(session, authz, actor, work_id,
                                                   ApplyPsdImport(export_run_id=run_id, page_id=page_id,
                                                                  entries=entries))
    held = (await session.execute(select(HeldAiChange).where(
        HeldAiChange.page_id == page_id, HeldAiChange.status == "open",
        HeldAiChange.payload["export_run_id"].as_string() == run_id))).scalars().all()
    return {"event_id": event.id,
            "matches": {k: sum(1 for m in matches if m.kind == k)
                        for k in ("unchanged", "changed", "renamed", "new", "missing")},
            "held": [row(h, "id", "kind", "target_table", "target_id", "choices", "payload") for h in held]}
