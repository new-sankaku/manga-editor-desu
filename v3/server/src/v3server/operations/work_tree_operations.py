"""巻・話・ページ・コマを足す・変える・抜く操作。"""


from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.work_tree_tables import Episode, Page, Panel, Volume
from v3server.openfga_permissions import Tuple
from v3server.operations.operation_base import (
    OpBase,
    Scope,
    _changed,
    get_in_work,
    page_obj,
    work_obj,
)
from v3server.v3_error_types import Invalid


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
