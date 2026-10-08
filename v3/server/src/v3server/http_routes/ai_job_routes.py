"""今のアプリの機能を移した、AIへ頼む口（V3細部の決めごと 10.4）。どれも依頼の順番待ち（job_start_and_control.enqueue）を通す
（送り先・送ってよい先・作業のAIの関与・権限が同じにかかる。何の作業の処理かは generation_queue/known_processes.py）。

- POST /works/{id}/images/{image_id}/read-prompt：絵から指示文を読む（read_prompt）。答えは依頼の result.read
- POST /works/{id}/plan/extract-characters：企画から人物を抜き出す（extract_characters）。答えの人物はAIの案として設定資料に入る
- POST /works/{id}/annotations/{annotation_id}/job：赤入れから依頼を作る。処理と依頼の中身は人が選ぶ。
  依頼には赤入れの文と範囲を annotation として添え、作った依頼を赤入れに残す（RecordAnnotationJob）
- 絵の角度を変える（change_angle）・背景を消す（remove_background）は、POST /works/{id}/jobs にその処理の名前で頼む
  （中身のグラフはつなぎ先ごとの処理の登録が持つ）
"""

import base64
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.material_and_setting_tables import MaterialEntry, WorkPlan
from v3server.canonical_tables.page_item_tables import AnnotationItem
from v3server.generation_queue import job_start_and_control
from v3server.http_routes.http_dependencies import ActorDep, AuthzDep, SessionDep, TemporalDep, require, row
from v3server.http_routes.job_routes import JOB_FIELDS
from v3server.image_file_storage import read_image
from v3server.llm_questions.extract_characters_question import build_extract_characters_question
from v3server.llm_questions.read_prompt_question import build_read_prompt_question
from v3server.operations import operation_submit_and_undo
from v3server.operations.annotation_operations import RecordAnnotationJob
from v3server.operations.operation_base import get_in_work, work_obj
from v3server.v3_error_types import Invalid

router = APIRouter()


class ReadPromptBody(BaseModel):
    style_note: str | None = None
    params: dict[str, Any] = {}


@router.post("/works/{work_id}/images/{image_id}/read-prompt", status_code=201)
async def read_prompt(work_id: str, image_id: str, body: ReadPromptBody, session: SessionDep, authz: AuthzDep,
                      temporal: TemporalDep, actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    img = await get_in_work(session, ImageFile, image_id, work_id)
    url = f"data:{img.media_type};base64," + base64.b64encode(read_image(img.sha256)).decode()
    messages = [{"role": "user", "content": [{"type": "text", "text": build_read_prompt_question(body.style_note)},
                                             {"type": "image_url", "image_url": {"url": url}}]}]
    job = await job_start_and_control.enqueue(session, authz, temporal, actor, work_id, "read_prompt",
                                              {"messages": messages, "params": body.params, "image_id": image_id},
                                              "human", page_id=img.page_id)
    return row(job, *JOB_FIELDS)


class ExtractBody(BaseModel):
    params: dict[str, Any] = {}


@router.post("/works/{work_id}/plan/extract-characters", status_code=201)
async def extract_characters(work_id: str, body: ExtractBody, session: SessionDep, authz: AuthzDep,
                             temporal: TemporalDep, actor: ActorDep):
    plan = (await session.execute(select(WorkPlan).where(WorkPlan.work_id == work_id))).scalar_one_or_none()
    parts = [p for p in ((plan.synopsis, plan.audience, plan.notes) if plan else ()) if p]
    if not parts:
        raise Invalid("企画の文（あらすじ・読者・メモ）がまだ無い")
    names = [m.name for m in (await session.execute(select(MaterialEntry).where(
        MaterialEntry.work_id == work_id, MaterialEntry.kind == "character",
        MaterialEntry.removed.is_(False)))).scalars()]
    messages = [{"role": "user", "content": build_extract_characters_question("\n\n".join(parts), names)}]
    job = await job_start_and_control.enqueue(session, authz, temporal, actor, work_id, "extract_characters",
                                              {"messages": messages, "params": body.params}, "human")
    return row(job, *JOB_FIELDS)


class AnnotationJobBody(BaseModel):
    process: str
    request: dict[str, Any]


@router.post("/works/{work_id}/annotations/{annotation_id}/job", status_code=201)
async def annotation_job(work_id: str, annotation_id: str, body: AnnotationJobBody, session: SessionDep,
                         authz: AuthzDep, temporal: TemporalDep, actor: ActorDep):
    item = await get_in_work(session, AnnotationItem, annotation_id, work_id)
    if item.removed:
        raise Invalid("抜かれた赤入れ")
    if "annotation" in body.request:
        raise Invalid("annotation はサーバーが書く。依頼に入れられない")
    request = {**body.request, "annotation": {"id": item.id, "body": item.body, "region_mm": item.region_mm,
                                              "panel_id": item.panel_id}}
    job = await job_start_and_control.enqueue(session, authz, temporal, actor, work_id, body.process, request,
                                              "human", page_id=item.page_id)
    event = await operation_submit_and_undo.submit(session, authz, actor, work_id,
                                                   RecordAnnotationJob(id=item.id, job_id=job.id))
    return {"job": row(job, *JOB_FIELDS), "event_id": event.id}
