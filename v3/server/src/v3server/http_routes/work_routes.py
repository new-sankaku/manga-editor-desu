"""作品・参加者・操作・出来事の口。"""


from typing import Annotated, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from v3server.canonical_tables.episode_plan_tables import EpisodePlan, Foreshadowing
from v3server.canonical_tables.event_and_lock_tables import Event, UndoConflict
from v3server.canonical_tables.material_and_setting_tables import MaterialEntry, WorkPlan
from v3server.canonical_tables.page_item_tables import AnnotationItem, PageItem, PanelTemplate
from v3server.canonical_tables.service_and_job_tables import WorkDestination
from v3server.canonical_tables.text_and_layer_tables import PanelLayer, TextItem
from v3server.canonical_tables.threshold_and_finding_tables import Threshold
from v3server.canonical_tables.work_tree_tables import (
    Episode,
    Page,
    Panel,
    Spread,
    Volume,
    Work,
)
from v3server.http_routes.http_dependencies import (
    ActorDep,
    AuthzDep,
    SessionDep,
    require,
    row,
)
from v3server.openfga_permissions import Tuple
from v3server.operations import operation_submit_and_undo
from v3server.operations.ai_involvement import TASK_TITLES, TASKS, mode_of
from v3server.operations.all_operation_types import Op
from v3server.operations.operation_base import work_obj
from v3server.v3_error_types import NotFound

# ---------------------------------------------------------------- 作品


router = APIRouter()


class NewWork(BaseModel):
    title: str
    reading_direction: Literal["rtl", "ltr"]
    text_direction: Literal["vertical", "horizontal"]
    medium: Literal["paper", "web_page", "vertical_scroll"]
    trim_size: str | None = None
    default_page_count: int | None = None


@router.post("/works", status_code=201)
async def create_work(body: NewWork, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """作品を作った人が作者になる。作品が無い間は操作の窓口を通せないので、ここで最初の出来事を書く。"""
    work = Work(**body.model_dump())
    session.add(work)
    await session.flush()
    operation_submit_and_undo.append_event(session, work, actor, "create_work", body.model_dump())
    tuple_ = Tuple(f"user:{actor.id}", "author", work_obj(work.id))
    await authz.write([tuple_])
    try:
        await session.commit()
    except Exception:
        await authz.write(deletes=[tuple_])
        raise
    return {"id": work.id}


def all_columns(obj) -> dict:
    return {c.key: getattr(obj, c.key) for c in obj.__table__.columns}


# GET /works/{id} の表ごとの並び（無い表は主キーの順）
NATURAL_ORDER = {Volume: ("number",), Episode: ("volume_id", "number"), Page: ("episode_id", "number"),
                 Panel: ("page_id", "order"), TextItem: ("panel_id", "order"), PanelLayer: ("panel_id", "stack_order")}


@router.get("/works/{work_id}")
async def get_work(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    work = await session.get(Work, work_id)
    if work is None:
        raise NotFound(f"works:{work_id}")

    async def all_of(model):
        # 並びを決めて返す。ORDER BY が無いと、行を直した後（取り消しなど）に PostgreSQL の返す順が変わり、
        # 読む側が並びに頼ると時々違って見えた（取り込みの試験が3回に1回落ちた。2026-10-08）
        keys = [getattr(model, c) for c in NATURAL_ORDER.get(model, ())] + list(model.__mapper__.primary_key)
        return (await session.execute(select(model).where(model.work_id == work_id).order_by(*keys))).scalars().all()

    return {
        "work": row(work, "id", "title", "reading_direction", "text_direction", "medium", "trim_size",
                    "default_page_count", "page_spec", "first_page_is_left", "head_seq", "preferences"),
        "volumes": [row(v, "id", "number", "title", "removed") for v in await all_of(Volume)],
        "episodes": [row(e, "id", "volume_id", "number", "title", "deadline", "removed") for e in await all_of(Episode)],
        "pages": [row(p, "id", "episode_id", "number", "layout", "page_kind", "color_mode", "dpi", "nombre_display",
                      "human_hand_fields", "removed") for p in await all_of(Page)],
        "panels": [
            row(p, "id", "page_id", "order", "frame", "role", "content", "image_id", "image_placement",
                "frame_style", "adjustments", "fixed", "human_hand_fields", "human_confirmed", "removed")
            for p in await all_of(Panel)
        ],
        "text_items": [
            row(t, "id", "page_id", "panel_id", "item_kind", "order", "text", "speaker", "balloon_kind",
                "writing_direction", "font_size_pt", "box_mm", "tail_target_mm", "joined_to_previous",
                "font_family", "decoration", "ruby", "spans", "typesetting", "balloon_shape", "transform", "opacity",
                "adjustments", "fixed",
                "human_hand_fields", "removed")
            for t in await all_of(TextItem)
        ],
        "panel_layers": [
            row(la, "id", "page_id", "panel_id", "role", "image_id", "stack_order", "visible", "opacity", "placement",
                "adjustments", "fixed", "stroke_revision", "image_stroke_revision", "human_hand_fields", "removed")
            for la in await all_of(PanelLayer)
        ],
        # 10.4 で足した表は、列をそのまま返す。ペンの線は返さない（1冊分の点は大きすぎる）。
        # 線は層ごとに GET /works/{id}/layers/{layer_id}/pen-strokes で区切って取る（pen_stroke_routes.py）
        **{name: [all_columns(x) for x in await all_of(model)]
           for name, model in (("page_items", PageItem),
                               ("annotation_items", AnnotationItem), ("panel_templates", PanelTemplate),
                               ("material_entries", MaterialEntry), ("work_plans", WorkPlan),
                               ("spreads", Spread), ("episode_plans", EpisodePlan),
                               ("foreshadowings", Foreshadowing))},
        "thresholds": [row(t, "key", "value", "source", "status", "note") for t in await all_of(Threshold)],
        "destinations": [d.service_id for d in await all_of(WorkDestination)],
    }


@router.get("/works/{work_id}/ai-involvement")
async def get_ai_involvement(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """作業ごとのAIの関与。作品が選んでいない作業は設計の既定を返し、chosen=false で分かるようにする。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    work = await session.get(Work, work_id)
    if work is None:
        raise NotFound(f"works:{work_id}")
    out = []
    for task in TASKS:
        mode, chosen = mode_of(work, task)
        out.append({"task": task, "title": TASK_TITLES[task], "mode": mode, "chosen": chosen})
    return out


@router.get("/works/{work_id}/members")
async def get_members(work_id: str, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    return [
        {"user": t.user.removeprefix("user:"), "role": t.relation}
        for t in await authz.read(work_obj(work_id))
        if t.user.startswith("user:")
    ]


# ---------------------------------------------------------------- 操作と出来事


@router.post("/works/{work_id}/ops")
async def submit_op(work_id: str, op: Annotated[Op, Field(discriminator="type")], session: SessionDep,
                    authz: AuthzDep, actor: ActorDep):
    event = await operation_submit_and_undo.submit(session, authz, actor, work_id, op)
    # AIの変更が人の手の所に当たって判断待ちに置いた分（id・表・行・項目）。無ければ空
    return {"event_id": event.id, "seq": event.seq, "held_changes": event.held_changes or []}


@router.post("/works/{work_id}/events/{event_id}/undo")
async def undo_event(work_id: str, event_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    event = await operation_submit_and_undo.undo(session, authz, actor, work_id, event_id)
    return {"event_id": event.id, "seq": event.seq, "held_changes": event.held_changes or []}


@router.get("/works/{work_id}/events")
async def list_events(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep, after: int = 0,
                      limit: int = 200):
    await require(authz, actor, "can_view", work_obj(work_id))
    events = (
        await session.execute(
            select(Event).where(Event.work_id == work_id, Event.seq > after).order_by(Event.seq).limit(limit)
        )
    ).scalars().all()
    return [
        row(e, "id", "seq", "actor_kind", "actor_id", "on_behalf_of", "op_type", "payload", "undoes_event_id",
            "created_at") | {"undoable": e.inverse is not None, "held_changes": e.held_changes or []}
        for e in events
    ]


@router.get("/works/{work_id}/undo-conflicts")
async def list_undo_conflicts(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """後の変更を上書きするので止めた取り消しの記録（operations/field_change_record.py）。古い順。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    rows = (await session.execute(select(UndoConflict).where(UndoConflict.work_id == work_id)
                                  .order_by(UndoConflict.created_at))).scalars().all()
    return [row(c, "id", "event_id", "actor_kind", "actor_id", "conflicts", "created_at") for c in rows]
