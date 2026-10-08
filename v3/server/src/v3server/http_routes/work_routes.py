"""作品・参加者・操作・出来事の口。"""


from typing import Annotated, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from v3server.canonical_tables.event_and_lock_tables import Event
from v3server.canonical_tables.service_and_job_tables import WorkDestination
from v3server.canonical_tables.threshold_and_finding_tables import Threshold
from v3server.canonical_tables.work_tree_tables import (
    Episode,
    Page,
    Panel,
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


@router.get("/works/{work_id}")
async def get_work(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    work = await session.get(Work, work_id)
    if work is None:
        raise NotFound(f"works:{work_id}")

    async def all_of(model):
        return (await session.execute(select(model).where(model.work_id == work_id))).scalars().all()

    return {
        "work": row(work, "id", "title", "reading_direction", "text_direction", "medium", "trim_size",
                    "default_page_count", "head_seq"),
        "volumes": [row(v, "id", "number", "title", "removed") for v in await all_of(Volume)],
        "episodes": [row(e, "id", "volume_id", "number", "title", "deadline", "removed") for e in await all_of(Episode)],
        "pages": [row(p, "id", "episode_id", "number", "removed") for p in await all_of(Page)],
        "panels": [
            row(p, "id", "page_id", "order", "frame", "role", "content", "human_confirmed", "removed")
            for p in await all_of(Panel)
        ],
        "thresholds": [row(t, "key", "value", "source", "status", "note") for t in await all_of(Threshold)],
        "destinations": [d.service_id for d in await all_of(WorkDestination)],
    }


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
    return {"event_id": event.id, "seq": event.seq}


@router.post("/works/{work_id}/events/{event_id}/undo")
async def undo_event(work_id: str, event_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    event = await operation_submit_and_undo.undo(session, authz, actor, work_id, event_id)
    return {"event_id": event.id, "seq": event.seq}


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
            "created_at") | {"undoable": e.inverse is not None}
        for e in events
    ]
