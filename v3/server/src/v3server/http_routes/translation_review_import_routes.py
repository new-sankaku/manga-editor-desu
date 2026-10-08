"""今のアプリのプロジェクトの取り込み・訳文・確認の状態と進み具合の口（V3点検の結果 5章の6）。

- POST /works/{id}/episodes/{eid}/current-app-imports：今のアプリのプロジェクト（.lz4）を取り込む（作者だけ）。
  ファイルを読み、絵を入口に通し、行の案と報告を作って ImportCurrentAppProject を窓口に出す
- GET  /works/{id}/current-app-imports：取り込みの報告の一覧（新しい順。entries は返さず数だけ。?episode_id= で絞る）
- GET  /works/{id}/current-app-imports/{report_id}：取り込みの報告（入れた物・入れられなかった物と理由）
- GET  /works/{id}/translations?language=：言語ごとの訳文と、訳文の無い文字と、抜いた訳文
- GET  /works/{id}/review-records：確認の記録（コメントつき）
- GET  /works/{id}/progress：話ごとの進み具合と締切の見込み（未検証。review_progress.py）
訳文・確認の状態を変えるのは窓口の操作（set_text_translation・set_text_translation_removed・set_review_status）。
"""

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import ValidationError
from sqlalchemy import select

from v3server.canonical_tables.text_and_layer_tables import TextItem
from v3server.canonical_tables.translation_review_import_tables import (
    CurrentAppImportReport,
    ReviewRecord,
    TextItemTranslation,
)
from v3server.canonical_tables.work_tree_tables import Episode, Page, Work
from v3server.current_app_import.import_plan import (
    TakenImage,
    build_import_plan,
    referenced_image_keys,
)
from v3server.current_app_import.project_file_reader import (
    ProjectFileError,
    data_url_bytes,
    read_project_file,
)
from v3server.http_routes.http_dependencies import (
    ActorDep,
    AuthzDep,
    SessionDep,
    require,
    row,
)
from v3server.image_intake import take_in_image
from v3server.name_structure.reading_direction import PageSpec
from v3server.operations import operation_submit_and_undo
from v3server.operations.current_app_import_operations import ImportCurrentAppProject
from v3server.operations.operation_base import get_in_work, work_obj
from v3server.operations.text_translation_operations import LANGUAGE_PATTERN
from v3server.review_progress import work_progress
from v3server.server_settings import get_settings
from v3server.usage_terms_schema import UsageTerms
from v3server.v3_error_types import Invalid, NotFound

router = APIRouter()

REPORT_FIELDS = ("id", "work_id", "episode_id", "source_file_name", "source_sha256", "image_origin", "created_by",
                 "counts", "entries", "created_at")
TRANSLATION_FIELDS = ("id", "text_item_id", "page_id", "language", "text", "writing_direction", "font_size_pt",
                      "human_hand_fields")
RECORD_FIELDS = ("id", "target_kind", "target_id", "from_status", "to_status", "comment", "actor_kind", "actor_id",
                 "reverts_record_id", "created_at")


async def _work(session, work_id: str) -> Work:
    work = await session.get(Work, work_id)
    if work is None:
        raise NotFound(f"作品 {work_id}")
    return work


@router.post("/works/{work_id}/episodes/{episode_id}/current-app-imports", status_code=201)
async def import_current_app_project(
        work_id: str, episode_id: str, project: Annotated[UploadFile, File()],
        image_origin: Annotated[Literal["imported", "human_drawn"], Form()],
        session: SessionDep, authz: AuthzDep, actor: ActorDep,
        usage_terms: Annotated[str | None, Form()] = None):
    """image_origin：取り込む絵の出どころ（持ち込んだ絵か、人が描いた絵か）。imported は usage_terms（JSON）が要る。"""
    await require(authz, actor, "can_manage", work_obj(work_id))
    work = await _work(session, work_id)
    await get_in_work(session, Episode, episode_id, work_id)
    if work.page_spec is None:
        raise Invalid("作品のページの寸法（page_spec）を先に決める")
    terms = None
    if usage_terms is not None:
        try:
            terms = UsageTerms.model_validate_json(usage_terms)
        except ValidationError as e:
            raise Invalid(f"usage_terms の形が正しくない: {e.errors()[0]['msg']}") from e
    data = await project.read()
    name = project.filename or "project.lz4"
    try:
        parsed = read_project_file(data, get_settings().current_app_import_max_bytes)
    except (ProjectFileError, json.JSONDecodeError, UnicodeDecodeError) as e:
        raise Invalid(f"今のアプリのプロジェクトとして読めない: {e}") from e
    taken: dict[str, TakenImage] = {}
    for key, value in referenced_image_keys(parsed).items():
        try:
            stored = await take_in_image(session, work_id, data_url_bytes(value), "human_upload")
        except (ProjectFileError, Invalid) as e:
            # 読めない絵・入口で止めた絵は入れず、報告に理由を残す（import_plan.py）
            taken[key] = TakenImage(None, None, None, None, None, blocked=str(e))
            continue
        taken[key] = TakenImage(stored.sha256, stored.media_type, stored.width, stored.height, stored.dpi)
    sha = hashlib.sha256(data).hexdigest()
    plan = build_import_plan(parsed, PageSpec.model_validate(work.page_spec), work.reading_direction, taken, name,
                             f"今のアプリのプロジェクト {name}（sha256 {sha[:12]}）から取り込んだ")
    op = ImportCurrentAppProject(episode_id=episode_id, source_file_name=name, source_sha256=sha,
                                 image_origin=image_origin, usage_terms=terms, plan=plan)
    event = await operation_submit_and_undo.submit(session, authz, actor, work_id, op)
    report = await session.get(CurrentAppImportReport, op.report_id)
    return {"event_id": event.id, "page_ids": [p.id for p in plan.pages], **row(report, *REPORT_FIELDS)}


@router.get("/works/{work_id}/current-app-imports")
async def list_current_app_imports(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep,
                                   episode_id: str | None = None):
    await require(authz, actor, "can_view", work_obj(work_id))
    q = select(CurrentAppImportReport).where(CurrentAppImportReport.work_id == work_id)
    if episode_id is not None:
        q = q.where(CurrentAppImportReport.episode_id == episode_id)
    reports = (await session.execute(q.order_by(CurrentAppImportReport.created_at.desc()))).scalars().all()
    return [row(r, *(f for f in REPORT_FIELDS if f != "entries")) for r in reports]


@router.get("/works/{work_id}/current-app-imports/{report_id}")
async def get_current_app_import(work_id: str, report_id: str, session: SessionDep, authz: AuthzDep,
                                 actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    return row(await get_in_work(session, CurrentAppImportReport, report_id, work_id), *REPORT_FIELDS)


@router.get("/works/{work_id}/translations")
async def list_translations(work_id: str, language: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """言語の訳文と、訳文の無い文字（抜いていないページ・文字だけ）と、抜いた訳文。
    抜いた訳文のある文字へ足すと、その行を戻して書き直す（set_text_translation）。"""
    if not re.match(LANGUAGE_PATTERN, language):
        raise Invalid(f"言語の形が正しくない: {language}")
    await require(authz, actor, "can_view", work_obj(work_id))
    work = await _work(session, work_id)
    items = (await session.execute(select(TextItem).join(Page, Page.id == TextItem.page_id).where(
        TextItem.work_id == work_id, TextItem.removed.is_(False), Page.removed.is_(False)))).scalars().all()
    all_rows = (await session.execute(select(TextItemTranslation).where(
        TextItemTranslation.work_id == work_id, TextItemTranslation.language == language))).scalars().all()
    rows = {t.text_item_id: t for t in all_rows if not t.removed}
    removed = {t.text_item_id: t for t in all_rows if t.removed}
    return {"source_language": (work.preferences or {}).get("language"), "language": language,
            "translations": [row(rows[i.id], *TRANSLATION_FIELDS) | {"source_text": i.text}
                             for i in items if i.id in rows],
            "missing_text_item_ids": [i.id for i in items if i.id not in rows],
            "removed_translations": [row(removed[i.id], *TRANSLATION_FIELDS) | {"source_text": i.text}
                                     for i in items if i.id in removed]}


@router.get("/works/{work_id}/review-records")
async def list_review_records(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep,
                              target_id: str | None = None):
    await require(authz, actor, "can_view", work_obj(work_id))
    q = select(ReviewRecord).where(ReviewRecord.work_id == work_id)
    if target_id is not None:
        q = q.where(ReviewRecord.target_id == target_id)
    return [row(r, *RECORD_FIELDS) for r in (await session.execute(q.order_by(ReviewRecord.created_at))).scalars()]


@router.get("/works/{work_id}/progress")
async def get_progress(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    return await work_progress(session, await _work(session, work_id), datetime.now(UTC))
