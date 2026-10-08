"""絵のファイルの口。人が描いた絵・外から持ち込んだ絵・人が手を入れた絵を受け取る。生成した絵は順番待ちの作業者が同じ操作で登録する。
どの絵も入口（image_intake.py）を通る。版の出どころ・人の手の範囲・判断待ちもここで読む。"""

import json
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy import select

from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.text_and_layer_tables import (
    HeldAiChange,
    ProtectedRegion,
)
from v3server.canonical_tables.work_tree_tables import Episode, Panel
from v3server.http_routes.http_dependencies import (
    ActorDep,
    AuthzDep,
    SessionDep,
    require,
    row,
)
from v3server.image_file_storage import read_image
from v3server.image_intake import take_in_image
from v3server.operations import operation_submit_and_undo
from v3server.operations.image_file_operations import ImageRole, RegisterImage
from v3server.operations.image_provenance import episode_image_provenance, lineage
from v3server.operations.operation_base import get_in_work, work_obj
from v3server.operations.work_tree_operations import UpdatePanel
from v3server.usage_terms_schema import UsageTerms
from v3server.v3_error_types import Invalid

router = APIRouter()

IMAGE_FIELDS = ("id", "page_id", "panel_id", "role", "origin", "job_id", "based_on_image_id", "source_note",
                "usage_terms", "registered_by_kind", "registered_by_id", "sha256", "media_type", "width", "height", "dpi",
                "details", "created_at")
HumanOrigin = Literal["human_drawn", "imported", "human_edited"]


def _usage_terms(text: str | None) -> UsageTerms | None:
    if text is None:
        return None
    try:
        return UsageTerms.model_validate(json.loads(text))
    except (ValueError, ValidationError) as e:
        raise Invalid(f"usage_terms が正しくない: {e}") from e


async def _upload(session, authz, actor, work_id: str, image: UploadFile, role: str, origin: str, page_id, panel_id,
                  source_note, based_on_image_id, usage_terms) -> tuple[RegisterImage, str]:
    await require(authz, actor, "can_view", work_obj(work_id))
    terms = _usage_terms(usage_terms)
    stored = await take_in_image(session, work_id, await image.read(), "human_upload")
    op = RegisterImage(role=role, origin=origin, page_id=page_id, panel_id=panel_id, source_note=source_note,
                       based_on_image_id=based_on_image_id, usage_terms=terms, sha256=stored.sha256,
                       media_type=stored.media_type, width=stored.width, height=stored.height, dpi=stored.dpi,
                       details={"file_name": image.filename})
    event = await operation_submit_and_undo.submit(session, authz, actor, work_id, op)
    return op, event.id


@router.post("/works/{work_id}/images", status_code=201)
async def upload_image(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep,
                       image: Annotated[UploadFile, File()],
                       role: Annotated[ImageRole, Form()],
                       origin: Annotated[HumanOrigin, Form()],
                       page_id: Annotated[str | None, Form()] = None,
                       panel_id: Annotated[str | None, Form()] = None,
                       source_note: Annotated[str | None, Form()] = None,
                       based_on_image_id: Annotated[str | None, Form()] = None,
                       usage_terms: Annotated[str | None, Form(description="UsageTerms の JSON")] = None):
    """人が描いた絵・持ち込んだ絵・前の版に手を入れた絵を置いて登録する。コマに使うかは、別に update_panel の image_id で選ぶ
    （まとめて行うのは /works/{id}/panels/{panel_id}/image）。"""
    op, event_id = await _upload(session, authz, actor, work_id, image, role, origin, page_id, panel_id, source_note,
                                 based_on_image_id, usage_terms)
    return {"id": op.id, "event_id": event_id, "sha256": op.sha256}


@router.post("/works/{work_id}/panels/{panel_id}/image", status_code=201)
async def replace_panel_image(work_id: str, panel_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep,
                              image: Annotated[UploadFile, File()],
                              origin: Annotated[HumanOrigin, Form()],
                              source_note: Annotated[str | None, Form()] = None,
                              usage_terms: Annotated[str | None, Form()] = None,
                              role: Annotated[ImageRole, Form()] = "panel_art"):
    """コマの絵を、置いた・持ち込んだ・手を入れた絵に替える。今の絵は消さず、新しい版の元（based_on_image_id）として残る。
    登録と選ぶのは2つの出来事。選ぶ方を取り消すと、前の絵に戻る。"""
    panel = await get_in_work(session, Panel, panel_id, work_id)
    previous = panel.image_id
    op, reg_event = await _upload(session, authz, actor, work_id, image, role, origin, None, panel_id, source_note,
                                  previous, usage_terms)
    event = await operation_submit_and_undo.submit(session, authz, actor, work_id,
                                                   UpdatePanel(id=panel_id, image_id=op.id))
    return {"id": op.id, "previous_image_id": previous, "register_event_id": reg_event, "select_event_id": event.id}


@router.get("/works/{work_id}/images")
async def list_images(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep,
                      panel_id: str | None = None):
    await require(authz, actor, "can_view", work_obj(work_id))
    q = select(ImageFile).where(ImageFile.work_id == work_id)
    if panel_id is not None:
        q = q.where(ImageFile.panel_id == panel_id)
    return [row(i, *IMAGE_FIELDS) for i in (await session.execute(q.order_by(ImageFile.created_at))).scalars()]


@router.get("/works/{work_id}/images/{image_id}/file")
async def get_image_file(work_id: str, image_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    img = await get_in_work(session, ImageFile, image_id, work_id)
    return Response(read_image(img.sha256), media_type=img.media_type)


@router.get("/works/{work_id}/images/{image_id}/lineage")
async def get_image_lineage(work_id: str, image_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """この版から元の版までの、誰が・どこから・どの条件で。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    return await lineage(session, await get_in_work(session, ImageFile, image_id, work_id))


@router.get("/works/{work_id}/episodes/{episode_id}/image-provenance")
async def get_episode_image_provenance(work_id: str, episode_id: str, session: SessionDep, authz: AuthzDep,
                                       actor: ActorDep):
    """どのコマ・層にどの出どころの絵を使っているか（V3細部の決めごと 20章の一覧の元）。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    await get_in_work(session, Episode, episode_id, work_id)
    return await episode_image_provenance(session, episode_id)


@router.get("/works/{work_id}/images/{image_id}/protected-regions")
async def list_protected_regions(work_id: str, image_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    q = select(ProtectedRegion).where(ProtectedRegion.work_id == work_id, ProtectedRegion.image_id == image_id)
    return [row(r, "id", "image_id", "polygon_px", "mask_sha256", "note", "created_by", "removed", "created_at")
            for r in (await session.execute(q.order_by(ProtectedRegion.created_at))).scalars()]


@router.get("/works/{work_id}/held-changes")
async def list_held_changes(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep,
                            status: str | None = "open"):
    """AIの案が人の手の所を変えようとして、判断待ちになっているもの。決めるのは操作 resolve_held_change。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    q = select(HeldAiChange).where(HeldAiChange.work_id == work_id)
    if status is not None:
        q = q.where(HeldAiChange.status == status)
    return [row(h, "id", "target_table", "target_id", "page_id", "field", "proposed_value", "current_value",
                "proposal_id", "status", "created_at")
            for h in (await session.execute(q.order_by(HeldAiChange.created_at))).scalars()]
