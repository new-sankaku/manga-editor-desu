"""操作の一覧。正本を変える手段はここにある操作だけ。

1つの操作が持つもの
- scope: 誰の権限で（relation・object）、どのロックに当たるか
- apply: 正本を変え、取り消すときに流す操作を返す（取り消せないものは None）

取り消しは、返した操作を同じ窓口に流すだけ。消さずに removed の印を切り替えるので、取り消しの取り消しもできる。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..actor import Actor
from ..authz import WORK_ROLES, Tuple
from ..errors import Invalid, NotFound
from ..models import (
    Episode,
    FindingReaction,
    Page,
    Panel,
    Service,
    Threshold,
    Volume,
    Work,
    WorkDestination,
    new_id,
)


@dataclass
class Scope:
    relation: str
    object: str
    # (target_kind, target_id)。どれか1つでも他の者がロックしていれば止める
    lock_targets: list[tuple[str, str]] = field(default_factory=list)
    # ページ全体を変える操作は、そのページの中のコマ・個別のロックにも当たる
    page_tree: str | None = None


@dataclass
class ApplyContext:
    session: AsyncSession
    work: Work
    actor: Actor
    tuple_writes: list[Tuple] = field(default_factory=list)
    tuple_deletes: list[Tuple] = field(default_factory=list)


async def get_in_work(session: AsyncSession, model, obj_id: str, work_id: str):
    obj = await session.get(model, obj_id)
    if obj is None or obj.work_id != work_id:
        raise NotFound(f"{model.__tablename__}:{obj_id}")
    return obj


def work_obj(work_id: str) -> str:
    return f"work:{work_id}"


def page_obj(page_id: str) -> str:
    return f"page:{page_id}"


class OpBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    async def scope(self, session: AsyncSession, work: Work) -> Scope:
        raise NotImplementedError

    async def apply(self, ctx: ApplyContext) -> dict[str, Any] | None:
        raise NotImplementedError


def _changed(obj, changes: dict[str, Any]) -> dict[str, Any]:
    """changes を当て、元の値を返す。"""
    before = {k: getattr(obj, k) for k in changes}
    for k, v in changes.items():
        setattr(obj, k, v)
    return before


# ---------------------------------------------------------------- 作品


class SetWorkSettings(OpBase):
    type: Literal["set_work_settings"] = "set_work_settings"
    title: str | None = None
    reading_direction: Literal["rtl", "ltr"] | None = None
    text_direction: Literal["vertical", "horizontal"] | None = None
    medium: Literal["paper", "web_page", "vertical_scroll"] | None = None
    trim_size: str | None = None
    default_page_count: int | None = None

    async def scope(self, session, work):
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        changes = self.model_dump(exclude={"type"}, exclude_unset=True)
        if not changes:
            raise Invalid("変える項目がない")
        before = _changed(ctx.work, changes)
        return {"type": self.type, **before}


class SetMember(OpBase):
    """作品に人を招く・外す。役ごとに1件。"""

    type: Literal["set_member"] = "set_member"
    user: str
    role: str
    granted: bool

    async def scope(self, session, work):
        if self.role not in WORK_ROLES:
            raise Invalid(f"役が無い: {self.role}")
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        t = Tuple(f"user:{self.user}", self.role, work_obj(ctx.work.id))
        (ctx.tuple_writes if self.granted else ctx.tuple_deletes).append(t)
        return {**self.model_dump(), "granted": not self.granted}


class AllowDestination(OpBase):
    """作品の送ってよい先に API のつなぎ先を足す・外す。"""

    type: Literal["allow_destination"] = "allow_destination"
    service_id: str
    allowed: bool

    async def scope(self, session, work):
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        service = await ctx.session.get(Service, self.service_id)
        if service is None:
            raise NotFound(f"services:{self.service_id}")
        if service.location != "api":
            raise Invalid("手元のつなぎ先は常に送ってよい。足す・外すのはAPIだけ")
        row = await ctx.session.get(WorkDestination, (ctx.work.id, self.service_id))
        if self.allowed and row is None:
            ctx.session.add(WorkDestination(work_id=ctx.work.id, service_id=self.service_id))
        elif not self.allowed and row is not None:
            await ctx.session.delete(row)
        return {**self.model_dump(), "allowed": not self.allowed}


class SetThreshold(OpBase):
    """閾値を置く・変える・外す（value が None で外す）。"""

    type: Literal["set_threshold"] = "set_threshold"
    key: str
    value: dict[str, Any] | None
    source: str | None = None
    status: Literal["unverified", "verified", "rejected"] | None = None
    note: str | None = None

    async def scope(self, session, work):
        if self.value is not None and (self.source is None or self.status is None):
            raise Invalid("閾値には出典と検証の状態が要る")
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        row = (
            await ctx.session.execute(
                select(Threshold).where(Threshold.work_id == ctx.work.id, Threshold.key == self.key)
            )
        ).scalar_one_or_none()
        if row is None:
            inverse = {"type": self.type, "key": self.key, "value": None}
        else:
            inverse = {
                "type": self.type,
                "key": self.key,
                "value": row.value,
                "source": row.source,
                "status": row.status,
                "note": row.note,
            }
        if self.value is None:
            if row is not None:
                await ctx.session.delete(row)
        elif row is None:
            ctx.session.add(
                Threshold(
                    work_id=ctx.work.id,
                    key=self.key,
                    value=self.value,
                    source=self.source,
                    status=self.status,
                    note=self.note,
                )
            )
        else:
            row.value, row.source, row.status, row.note = self.value, self.source, self.status, self.note
        return inverse


class RecordFindingReaction(OpBase):
    """検査の指摘に人がどう反応したか。記録なので取り消さない（違えば反応を足し直す）。"""

    type: Literal["record_finding_reaction"] = "record_finding_reaction"
    finding_key: str
    target_kind: Literal["page", "panel", "item"]
    target_id: str
    reaction: Literal["fixed", "ignored", "disagreed"]
    note: str | None = None

    async def scope(self, session, work):
        return Scope("can_view", work_obj(work.id))

    async def apply(self, ctx):
        ctx.session.add(
            FindingReaction(
                work_id=ctx.work.id,
                finding_key=self.finding_key,
                target_kind=self.target_kind,
                target_id=self.target_id,
                reaction=self.reaction,
                actor_id=ctx.actor.id,
                note=self.note,
            )
        )
        return None


# ---------------------------------------------------------------- 巻・話・ページ


class AddVolume(OpBase):
    type: Literal["add_volume"] = "add_volume"
    id: str = Field(default_factory=new_id)
    number: int
    title: str | None = None

    async def scope(self, session, work):
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        ctx.session.add(Volume(id=self.id, work_id=ctx.work.id, number=self.number, title=self.title))
        return {"type": "set_removed", "target_kind": "volume", "id": self.id, "removed": True}


class AddEpisode(OpBase):
    type: Literal["add_episode"] = "add_episode"
    id: str = Field(default_factory=new_id)
    volume_id: str
    number: int
    title: str | None = None
    deadline: datetime | None = None

    async def scope(self, session, work):
        await get_in_work(session, Volume, self.volume_id, work.id)
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        ctx.session.add(
            Episode(
                id=self.id,
                work_id=ctx.work.id,
                volume_id=self.volume_id,
                number=self.number,
                title=self.title,
                deadline=self.deadline,
            )
        )
        return {"type": "set_removed", "target_kind": "episode", "id": self.id, "removed": True}


class UpdateEpisode(OpBase):
    type: Literal["update_episode"] = "update_episode"
    id: str
    title: str | None = None
    number: int | None = None
    deadline: datetime | None = None

    async def scope(self, session, work):
        await get_in_work(session, Episode, self.id, work.id)
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        episode = await ctx.session.get(Episode, self.id)
        changes = self.model_dump(exclude={"type", "id"}, exclude_unset=True)
        if not changes:
            raise Invalid("変える項目がない")
        before = _changed(episode, changes)
        return {"type": self.type, "id": self.id, **{k: _jsonable(v) for k, v in before.items()}}


class AddPage(OpBase):
    type: Literal["add_page"] = "add_page"
    id: str = Field(default_factory=new_id)
    episode_id: str
    number: int

    async def scope(self, session, work):
        await get_in_work(session, Episode, self.episode_id, work.id)
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        ctx.session.add(Page(id=self.id, work_id=ctx.work.id, episode_id=self.episode_id, number=self.number))
        ctx.tuple_writes.append(Tuple(work_obj(ctx.work.id), "work", page_obj(self.id)))
        return {"type": "set_removed", "target_kind": "page", "id": self.id, "removed": True}


class AssignPage(OpBase):
    """アシスタントにページを割り当てる・外す。"""

    type: Literal["assign_page"] = "assign_page"
    page_id: str
    user: str
    assigned: bool

    async def scope(self, session, work):
        await get_in_work(session, Page, self.page_id, work.id)
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        t = Tuple(f"user:{self.user}", "assigned", page_obj(self.page_id))
        (ctx.tuple_writes if self.assigned else ctx.tuple_deletes).append(t)
        return {**self.model_dump(), "assigned": not self.assigned}


# ---------------------------------------------------------------- コマ


class AddPanel(OpBase):
    type: Literal["add_panel"] = "add_panel"
    id: str = Field(default_factory=new_id)
    page_id: str
    order: int
    frame: dict[str, Any] = Field(default_factory=dict)
    role: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)

    async def scope(self, session, work):
        await get_in_work(session, Page, self.page_id, work.id)
        return Scope("can_draw", page_obj(self.page_id), [("page", self.page_id)])

    async def apply(self, ctx):
        ctx.session.add(
            Panel(
                id=self.id,
                work_id=ctx.work.id,
                page_id=self.page_id,
                order=self.order,
                frame=self.frame,
                role=self.role,
                content=self.content,
            )
        )
        return {"type": "set_removed", "target_kind": "panel", "id": self.id, "removed": True}


class UpdatePanel(OpBase):
    type: Literal["update_panel"] = "update_panel"
    id: str
    order: int | None = None
    frame: dict[str, Any] | None = None
    role: str | None = None
    content: dict[str, Any] | None = None
    human_confirmed: bool | None = None

    async def scope(self, session, work):
        panel = await get_in_work(session, Panel, self.id, work.id)
        return Scope("can_draw", page_obj(panel.page_id), [("page", panel.page_id), ("panel", panel.id)])

    async def apply(self, ctx):
        panel = await ctx.session.get(Panel, self.id)
        changes = self.model_dump(exclude={"type", "id"}, exclude_unset=True)
        if not changes:
            raise Invalid("変える項目がない")
        before = _changed(panel, changes)
        return {"type": self.type, "id": self.id, **before}


# ---------------------------------------------------------------- 抜く・戻す


_REMOVABLE = {"volume": Volume, "episode": Episode, "page": Page, "panel": Panel}


class SetRemoved(OpBase):
    """巻・話・ページ・コマを抜く・戻す。消さない（ごみ箱。V3細部の決めごと 18章）。"""

    type: Literal["set_removed"] = "set_removed"
    target_kind: Literal["volume", "episode", "page", "panel"]
    id: str
    removed: bool

    async def scope(self, session, work):
        obj = await get_in_work(session, _REMOVABLE[self.target_kind], self.id, work.id)
        if self.target_kind == "panel":
            return Scope("can_draw", page_obj(obj.page_id), [("page", obj.page_id), ("panel", obj.id)])
        if self.target_kind == "page":
            return Scope("can_manage", work_obj(work.id), [("page", obj.id)], page_tree=obj.id)
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        obj = await ctx.session.get(_REMOVABLE[self.target_kind], self.id)
        if obj.removed == self.removed:
            raise Invalid("すでにその状態")
        obj.removed = self.removed
        return {**self.model_dump(), "removed": not self.removed}


def _jsonable(v):
    return v.isoformat() if isinstance(v, datetime) else v


Op = Annotated[
    Union[
        SetWorkSettings,
        SetMember,
        AllowDestination,
        SetThreshold,
        RecordFindingReaction,
        AddVolume,
        AddEpisode,
        UpdateEpisode,
        AddPage,
        AssignPage,
        AddPanel,
        UpdatePanel,
        SetRemoved,
    ],
    Field(discriminator="type"),
]

op_adapter: TypeAdapter[Op] = TypeAdapter(Op)
