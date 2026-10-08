"""書き出しの口（V3細部の決めごと 10.4 の書き出し）と、人が直した PSD を戻す口。

- POST /works/{id}/exports：書き出しの依頼（ExportRun）を作り、書き出しの待ち行列に入れる（print_export/export_workflow.py）
  - 権限：PNG・PDF は作品を見られる人、PSD は書き出すページをどれも描ける人（PSD は直して戻すための書き出し）
  - 解像度（dpi）は任意。渡すと全ページをその解像度で出す（下見など）。無ければページごとの解像度（ページの dpi か作品の
    preferences.print）。紙の大きさ（paper_mm）は任意（無ければ塗り足し込みのページの大きさ）
  - 見開きのページを含むときは spread_output（split・joined・both）が要る（print_export/export_runner.py）
- GET /works/{id}/exports/{run_id}：状態と出力の一覧。PSD はペンの線が画素になることを note で返す（画面に出す文）
- GET /works/{id}/exports/{run_id}/files/{name}：書き出したファイル
- POST /works/{id}/exports/{run_id}/pages/{page_id}/psd：直した PSD を戻す（operations/psd_import_operations.py）。
  見開きを1枚にした PSD は戻せない（未対応）
- POST /works/{id}/preflight：入稿前の確かめ（print_export/preflight_checks.py）。ページごとの問題と場所を返す
"""

import io
import pathlib
from typing import Annotated, Literal

import numpy as np
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse
from PIL import Image
from pydantic import BaseModel, Field
from sqlalchemy import select
from temporalio.common import Priority

from v3server.canonical_tables.material_and_setting_tables import ExportRun
from v3server.canonical_tables.text_and_layer_tables import HeldAiChange, TextItem
from v3server.canonical_tables.work_tree_tables import Page, Work
from v3server.http_routes.http_dependencies import ActorDep, AuthzDep, SessionDep, TemporalDep, require, row
from v3server.image_file_storage import read_image, staged_file
from v3server.image_intake import take_in_image
from v3server.name_structure.reading_direction import PageSpec
from v3server.operations import operation_submit_and_undo
from v3server.operations.operation_base import get_in_work, page_obj, work_obj
from v3server.operations.pen_stroke_operations import StoredResult
from v3server.operations.psd_import_operations import (
    MODELS,
    SUFFIX_TABLE,
    ApplyPsdImport,
    PsdImportEntry,
    split_marker,
)
from v3server.operations.text_translation_operations import LANGUAGE_PATTERN
from v3server.print_export.export_runner import PSD_STROKE_NOTE, ExportRefused, translated_texts
from v3server.print_export.export_workflow import EXPORT_QUEUE, ExportRunWorkflow
from v3server.print_export.page_render import mm_to_px_matrix
from v3server.print_export.preflight_checks import issues_json, run_preflight
from v3server.print_export.psd_import_matching import ExportedLayer, Match, import_actions, match_layers, read_psd
from v3server.print_export.text_render import font_path, measure_texts
from v3server.server_settings import get_settings
from v3server.v3_error_types import Invalid, NotFound

router = APIRouter()

# done_page_ids：描き終えたページ（進み具合。page_ids の数と比べる）
RUN_FIELDS = ("id", "work_id", "requested_by", "format", "page_ids", "dpi", "spread_output", "paper_mm", "language",
              "status", "detail", "outputs", "done_page_ids", "created_at", "updated_at")


class ExportRequest(BaseModel):
    format: Literal["png", "pdf", "psd"]
    page_ids: list[str] = Field(min_length=1)
    dpi: int | None = Field(default=None, gt=0, le=2400)
    spread_output: Literal["split", "joined", "both"] | None = None
    paper_mm: tuple[float, float] | None = None
    # 言語ごとの書き出し（訳文に差し替える。print_export/export_runner.py の translated_texts）。無ければ元の文字
    language: str | None = Field(default=None, pattern=LANGUAGE_PATTERN)


class PreflightRequest(BaseModel):
    # 確かめるページ。無ければ作品の抜いていない全ページ
    page_ids: list[str] | None = None
    # 言語ごとの書き出しの前の確かめ（訳文に差し替えて、はみ出し・書体に無い字・訳文の無い文字を見る）。無ければ元の文字
    language: str | None = Field(default=None, pattern=LANGUAGE_PATTERN)


async def _require_export(session, authz, actor, work_id: str, fmt: str, page_ids: list[str]) -> None:
    if fmt != "psd":
        await require(authz, actor, "can_view", work_obj(work_id))
        return
    for pid in page_ids:
        await require(authz, actor, "can_draw", page_obj(pid))


async def _check_language(session, work_id: str, req: ExportRequest) -> None:
    """言語の書き出しは、始める前に訳文の揃いを確かめる（足りなければ、足りない文字を挙げて止める）。"""
    work = await session.get(Work, work_id)
    if not (work.preferences or {}).get("language"):
        raise Invalid("作品の言語（preferences.language）が決まっていない。どれが元の言語か分からない")
    for pid in req.page_ids:
        page = await session.get(Page, pid)
        texts = (await session.execute(select(TextItem).where(
            TextItem.page_id == page.id, TextItem.removed.is_(False)))).scalars().all()
        try:
            await translated_texts(session, work, list(texts), req.language)
        except ExportRefused as e:
            raise Invalid(str(e)) from e


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
    if req.language is not None:
        await _check_language(session, work_id, req)
    run = ExportRun(work_id=work_id, requested_by=actor.id, format=req.format, page_ids=req.page_ids, dpi=req.dpi,
                    spread_output=req.spread_output,
                    paper_mm=list(req.paper_mm) if req.paper_mm else None, language=req.language, status="queued",
                    outputs=[])
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


@router.post("/works/{work_id}/preflight")
async def preflight(work_id: str, req: PreflightRequest, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """入稿前の確かめ。ページごとの問題（種類・重さ・場所）を返す。正本は変えない。"""
    work = await session.get(Work, work_id)
    if work is None:
        raise NotFound(f"作品 {work_id}")
    await require(authz, actor, "can_view", work_obj(work_id))
    if req.page_ids is not None:
        if len(set(req.page_ids)) != len(req.page_ids):
            raise Invalid("同じページが2回ある")
        for pid in req.page_ids:
            page = await get_in_work(session, Page, pid, work_id)
            if page.removed:
                raise Invalid(f"ページ {pid} は抜かれている")
    s = get_settings()
    if not s.text_render_script:
        raise Invalid("V3_TEXT_RENDER_SCRIPT が無い。文字の組み方を確かめられない")
    issues = await run_preflight(session, work, req.page_ids,
                                 lambda items: measure_texts(items, s.node_executable, s.text_render_script),
                                 lambda family: font_path(s.font_dir, family), req.language)
    return issues_json(issues)


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


async def spread_page_of(session, work_id: str, m: Match, pages: list[str], left: str, gutter_px: float) -> str:
    """見開きの PSD の層が、どちらのページの物か。印の行（コマ・層・文字・ページの物）のページ、新しい層は親のコマのページ。
    どちらとも決まらない層（見開きの絵・紙、コマの外の新しい層）は、層の真ん中がノドのどちら側か。"""
    marker = m.marker if m.kind != "new" else m.layer.parent_marker
    if marker is not None:
        base, suffix = split_marker(marker)
        if base in pages:
            return base
        table = SUFFIX_TABLE.get(suffix) if suffix else (m.exported.table if m.exported is not None else "panels")
        model = MODELS.get(table)
        if model is not None and model is not Page:
            obj = await session.get(model, base)
            if obj is not None and obj.work_id == work_id and obj.page_id in pages:
                return obj.page_id
    if m.layer is not None and m.layer.image is not None:
        x0, x1 = m.layer.left, m.layer.left + m.layer.image.width
    else:
        x0, x1 = m.exported.left, m.exported.left + m.exported.image.width
    right = next(p for p in pages if p != left)
    return left if (x0 + x1) / 2 < gutter_px else right


@router.post("/works/{work_id}/exports/{run_id}/pages/{page_id}/psd")
async def import_psd(work_id: str, run_id: str, page_id: str, psd: Annotated[UploadFile, File()],
                     session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """直した PSD を戻す。結び付けは print_export/psd_import_matching.py、当て方は ApplyPsdImport。
    当てる権限とロックを、ファイルを書く前に確かめる。PSD は一時ファイルに写してから読み、大きさ・層の数・画素数の上限で止める。
    層の絵の判定の記録は、当てる出来事と同じ確定に入れる（途中で断られても記録だけ残らない）。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    work = await session.get(Work, work_id)
    run = await get_in_work(session, ExportRun, run_id, work_id)
    spread_out = next((o for o in run.outputs if page_id in (o.get("page_ids") or [])), None)
    other_page = next(p for p in spread_out["page_ids"] if p != page_id) if spread_out is not None else None
    await operation_submit_and_undo.check_may_submit(
        session, authz, actor, work,
        ApplyPsdImport(export_run_id=run_id, page_id=page_id, other_page_id=other_page, entries=[]))
    out = next((o for o in run.outputs if o.get("page_id") == page_id or page_id in (o.get("page_ids") or [])), None)
    if run.format != "psd" or run.status != "done" or out is None:
        raise Invalid("このページを PSD に書き出し終えた記録ではない")
    spread_pages = out.get("page_ids")
    if spread_pages is not None and "left_page_id" not in out:
        raise Invalid("この見開きの PSD は、左のページを記録する前に書き出した物で戻せない（書き出し直す）")
    exported = {la["marker"]: ExportedLayer(la["marker"], la["table"], la["left"], la["top"],
                                            Image.open(io.BytesIO(read_image(la["sha256"]))).convert("RGBA"))
                for la in out["layers"]}
    settings = get_settings()
    with staged_file(psd.file) as path:
        read = read_psd(path, max_pixels=settings.image_max_pixels, max_layers=settings.psd_max_layers)
    matches = match_layers(read, exported)
    spec = PageSpec.model_validate(work.page_spec)
    ox, oy = out["offset_px"]

    def px_to_mm_of(offset_x_mm: float):
        inv = np.linalg.inv(mm_to_px_matrix(spec, out["dpi"], offset_x_mm))

        def px_to_mm(x, y):
            v = inv @ np.array([x - ox, y - oy, 1.0])
            return float(v[0]), float(v[1])

        return px_to_mm

    if spread_pages is None:
        groups = {page_id: matches}
        offsets = {page_id: 0.0}
    else:
        left = out["left_page_id"]
        offsets = {pid: 0.0 if pid == left else spec.trim_width_mm for pid in spread_pages}
        # ノドの x（PSD の画素）：左のページの仕上がりの右の端
        fx, _ = spec.frame_origin_in_trim()
        gutter_px = float((mm_to_px_matrix(spec, out["dpi"]) @ np.array([spec.trim_width_mm - fx, 0.0, 1.0]))[0]) + ox
        groups = {pid: [] for pid in spread_pages}
        for m in matches:
            groups[await spread_page_of(session, work_id, m, spread_pages, left, gutter_px)].append(m)
    entries = []
    for pid, ms in groups.items():
        for a in import_actions(ms, px_to_mm_of(offsets[pid])):
            image = None
            if a.image is not None:
                buf = io.BytesIO()
                a.image.save(buf, format="PNG")
                stored = await take_in_image(session, work_id, buf.getvalue(), "human_upload", commit=False)
                image = StoredResult(sha256=stored.sha256, media_type=stored.media_type, width=stored.width,
                                     height=stored.height)
            entries.append(PsdImportEntry(kind=a.kind, marker=a.marker, table=a.table, image=image, box_mm=a.box_mm,
                                          parent_marker=a.parent_marker, layer_name=a.layer_name,
                                          page_id=pid if spread_pages is not None else None))
    event = await operation_submit_and_undo.submit(session, authz, actor, work_id,
                                                   ApplyPsdImport(export_run_id=run_id, page_id=page_id,
                                                                  other_page_id=other_page, entries=entries))
    held = (await session.execute(select(HeldAiChange).where(
        HeldAiChange.page_id.in_(spread_pages or [page_id]), HeldAiChange.status == "open",
        HeldAiChange.payload["export_run_id"].as_string() == run_id))).scalars().all()
    return {"event_id": event.id,
            "matches": {k: sum(1 for m in matches if m.kind == k)
                        for k in ("unchanged", "changed", "renamed", "new", "missing")},
            "held": [row(h, "id", "kind", "target_table", "target_id", "choices", "payload") for h in held]}
