"""絵のファイルの口。人が描いた絵・外から持ち込んだ絵を受け取る。生成した絵は順番待ちの作業者が同じ操作で登録する。"""

from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import Response
from sqlalchemy import select

from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.http_routes.http_dependencies import (
    ActorDep,
    AuthzDep,
    SessionDep,
    require,
    row,
)
from v3server.image_file_storage import read_image, store_image
from v3server.operations import operation_submit_and_undo
from v3server.operations.image_file_operations import ImageRole, RegisterImage
from v3server.operations.operation_base import get_in_work, work_obj

router = APIRouter()

IMAGE_FIELDS = ("id", "page_id", "panel_id", "role", "origin", "job_id", "source_note", "registered_by_kind",
                "registered_by_id", "sha256", "media_type", "width", "height", "dpi", "details", "created_at")


@router.post("/works/{work_id}/images", status_code=201)
async def upload_image(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep,
                       image: Annotated[UploadFile, File()],
                       role: Annotated[ImageRole, Form()],
                       origin: Annotated[Literal["human_drawn", "imported"], Form()],
                       page_id: Annotated[str | None, Form()] = None,
                       panel_id: Annotated[str | None, Form()] = None,
                       source_note: Annotated[str | None, Form()] = None):
    """人が描いた絵か、外から持ち込んだ絵を置いて登録する。コマに使うかは、別に update_panel の image_id で選ぶ。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    stored = store_image(await image.read())
    op = RegisterImage(role=role, origin=origin, page_id=page_id, panel_id=panel_id, source_note=source_note,
                       sha256=stored.sha256, media_type=stored.media_type, width=stored.width, height=stored.height,
                       dpi=stored.dpi, details={"file_name": image.filename})
    event = await operation_submit_and_undo.submit(session, authz, actor, work_id, op)
    return {"id": op.id, "event_id": event.id, "sha256": stored.sha256}


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
