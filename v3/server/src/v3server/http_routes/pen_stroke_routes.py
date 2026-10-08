"""ペン・消しゴムの口のうち、絵を受け取る・作るもの（V3細部の決めごと 10.1）。線そのものの操作（足す・選んで変える・消す・
線の消しゴム）は POST /works/{id}/ops に add_pen_strokes などを送る（operations/pen_stroke_operations.py）。

- POST /works/{id}/layers/{layer_id}/stroke-cache：画面が線から描いた控えの絵を上げる（SetStrokeCache）。
  控えは画面が描く（今のアプリの筆を画面が持っているので、見えている絵と控えが同じになる）。サーバーは筆を描かない
- POST /works/{id}/panels/{panel_id}/erase-pixels：線を持たない絵を画素の消しゴムで消す（ErasePixels）。
  消した後の絵と消した所のマスクはここで作り、入口を通して置く
- GET /works/{id}/panels/{panel_id}/layers：そのコマの層だけ（作品全体を読み直さずに、変わったコマだけを取る）
- GET /works/{id}/layers/{layer_id}/pen-strokes：その層の線を重ねる順に、区切って返す（after・limit）。
  作品全体の口（GET /works/{id}）は線を返さない（1冊分の線の点は大きすぎる）
"""

import json
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select

from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.page_item_tables import PenStroke
from v3server.canonical_tables.text_and_layer_tables import PanelLayer
from v3server.canonical_tables.work_tree_tables import Panel
from v3server.hand_tools.pen_stroke_raster import PixelEraserStroke, erase_pixels
from v3server.http_routes.http_dependencies import ActorDep, AuthzDep, SessionDep, require, row
from v3server.image_file_storage import read_image, store_image
from v3server.image_intake import take_in_image
from v3server.operations import operation_submit_and_undo
from v3server.operations.operation_base import get_in_work, page_obj, work_obj
from v3server.operations.pen_stroke_operations import ErasePixels, SetStrokeCache, StoredResult
from v3server.v3_error_types import Invalid

router = APIRouter()

_STROKES = TypeAdapter(list[PixelEraserStroke])


def _json(text: str, what: str):
    try:
        return json.loads(text)
    except ValueError as e:
        raise Invalid(f"{what} が JSON ではない: {e}") from e


@router.post("/works/{work_id}/layers/{layer_id}/stroke-cache")
async def upload_stroke_cache(work_id: str, layer_id: str, image: Annotated[UploadFile, File()],
                              stroke_revision: Annotated[int, Form()], placement: Annotated[str, Form()],
                              session: SessionDep, authz: AuthzDep, actor: ActorDep):
    layer = await get_in_work(session, PanelLayer, layer_id, work_id)
    # 入口に置く前に確かめる（操作の入口でも同じ確認をする）
    await require(authz, actor, "can_draw", page_obj(layer.page_id))
    stored = await take_in_image(session, work_id, await image.read(), "human_upload")
    op = SetStrokeCache(layer_id=layer_id, stroke_revision=stroke_revision, placement=_json(placement, "placement"),
                        result=StoredResult(sha256=stored.sha256, media_type=stored.media_type, width=stored.width,
                                            height=stored.height))
    event = await operation_submit_and_undo.submit(session, authz, actor, work_id, op)
    return {"event_id": event.id, "image_id": op.image_id}


@router.post("/works/{work_id}/panels/{panel_id}/erase-pixels")
async def erase_image_pixels(work_id: str, panel_id: str, strokes: Annotated[str, Form()],
                             session: SessionDep, authz: AuthzDep, actor: ActorDep,
                             layer_id: Annotated[str | None, Form()] = None):
    try:
        parsed = _STROKES.validate_python(_json(strokes, "strokes"))
    except ValidationError as e:
        raise Invalid(f"strokes が正しくない: {e}") from e
    if not parsed:
        raise Invalid("消しゴムの線が無い")
    panel = await get_in_work(session, Panel, panel_id, work_id)
    await require(authz, actor, "can_draw", page_obj(panel.page_id))
    target = await get_in_work(session, PanelLayer, layer_id, work_id) if layer_id else panel
    if target.image_id is None:
        raise Invalid("消す絵が無い")
    base = await get_in_work(session, ImageFile, target.image_id, work_id)
    png, mask = erase_pixels(read_image(base.sha256), parsed)
    stored = await take_in_image(session, work_id, png, "human_upload")
    mask_stored = store_image(mask)
    op = ErasePixels(panel_id=panel.id, layer_id=layer_id, base_image_id=base.id, strokes=parsed,
                     result=StoredResult(sha256=stored.sha256, media_type=stored.media_type, width=stored.width,
                                         height=stored.height), erase_mask_sha256=mask_stored.sha256)
    event = await operation_submit_and_undo.submit(session, authz, actor, work_id, op)
    return {"event_id": event.id, "image_id": op.result_image_id}


LAYER_FIELDS = ("id", "page_id", "panel_id", "role", "image_id", "stack_order", "visible", "opacity", "placement",
                "adjustments", "fixed", "stroke_revision", "image_stroke_revision", "human_hand_fields", "removed")
STROKE_FIELDS = ("id", "layer_id", "stack_order", "brush", "points", "width_mm", "color", "opacity", "seed",
                 "brush_options", "pointer_type", "fixed", "human_hand_fields")


@router.get("/works/{work_id}/panels/{panel_id}/layers")
async def panel_layers(work_id: str, panel_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    panel = await get_in_work(session, Panel, panel_id, work_id)
    q = select(PanelLayer).where(PanelLayer.panel_id == panel.id).order_by(PanelLayer.stack_order)
    return {"panel": row(panel, "id", "page_id", "order", "image_id", "image_placement", "removed"),
            "layers": [row(la, *LAYER_FIELDS) for la in (await session.execute(q)).scalars()]}


@router.get("/works/{work_id}/layers/{layer_id}/pen-strokes")
async def layer_pen_strokes(work_id: str, layer_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep,
                            after: int = -1, limit: Annotated[int, Query(ge=1, le=2000)] = 500,
                            points: bool = True):
    """抜いていない線を stack_order の順に返す。next_after が null でなければ、after=next_after で続きを取る。
    points=false なら点を省く（画面が持っている線と同じかを確かめるとき）。stroke_revision は読んだ時点の層の線の版。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    layer = await get_in_work(session, PanelLayer, layer_id, work_id)
    q = (select(PenStroke).where(PenStroke.layer_id == layer.id, PenStroke.removed.is_(False),
                                 PenStroke.stack_order > after)
         .order_by(PenStroke.stack_order, PenStroke.id).limit(limit + 1))
    rows = list((await session.execute(q)).scalars())
    more = len(rows) > limit
    rows = rows[:limit]
    fields = STROKE_FIELDS if points else tuple(f for f in STROKE_FIELDS if f != "points")
    return {"layer_id": layer.id, "stroke_revision": layer.stroke_revision,
            "image_stroke_revision": layer.image_stroke_revision,
            "strokes": [row(s, *fields) for s in rows],
            "next_after": rows[-1].stack_order if more else None}
