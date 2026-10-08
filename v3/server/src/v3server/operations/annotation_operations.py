"""赤入れ（AnnotationItem）を付ける・直す・済ませる操作（V3細部の決めごと 10.4 の赤入れ、V3ハーネス設計 9.4）。

人もAIも付けられる。AIが付けるのは、その作業（about_task）の検査（check）の関与で許されているときだけ。
赤入れから AIへの指示（依頼）を作るのは http_routes/annotation_routes.py。作った依頼は job_ids に残す（RecordAnnotationJob）。
"""

from typing import Literal

from pydantic import Field

from v3server.canonical_tables.page_item_tables import AnnotationItem
from v3server.canonical_tables.service_and_job_tables import Job
from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.work_tree_tables import Page, Panel
from v3server.operations.ai_involvement import Task, require_actor_may
from v3server.operations.operation_base import OpBase, Scope, get_in_work, work_obj
from v3server.operations.row_snapshot import RowChanges
from v3server.v3_error_types import Invalid

Polygon = list[tuple[float, float]]


def _region(region: Polygon | None) -> list[list[float]] | None:
    if region is None:
        return None
    if len(region) < 3:
        raise Invalid("範囲は3つ以上の点で囲む")
    return [[float(x), float(y)] for x, y in region]


class AddAnnotation(OpBase):
    type: Literal["add_annotation"] = "add_annotation"
    id: str = Field(default_factory=new_id)
    page_id: str
    panel_id: str | None = None
    region_mm: Polygon | None = None
    body: str = Field(min_length=1)
    about_task: Task

    ai_may_submit = True

    async def scope(self, session, work):
        await get_in_work(session, Page, self.page_id, work.id)
        if self.panel_id is not None:
            panel = await get_in_work(session, Panel, self.panel_id, work.id)
            if panel.page_id != self.page_id:
                raise Invalid("コマとページが合わない")
        return Scope("can_comment", work_obj(work.id), [("page", self.page_id)])

    async def apply(self, ctx):
        require_actor_may(ctx.actor, ctx.work, self.about_task, "check")
        is_human = ctx.actor.kind == "human"
        rc = RowChanges(ctx)
        rc.created(AnnotationItem(id=self.id, work_id=ctx.work.id, page_id=self.page_id, panel_id=self.panel_id,
                                  region_mm=_region(self.region_mm), body=self.body, about_task=self.about_task,
                                  author_kind=ctx.actor.kind, author_id=ctx.actor.id, status="open", job_ids=[],
                                  removed=False,
                                  human_hand_fields=["about_task", "body", "region_mm"] if is_human else []))
        return rc.inverse([self.page_id], "赤入れを付けた取り消し")


class UpdateAnnotation(OpBase):
    """赤入れの中身・範囲・作業を直す。済んだ（resolved）・開き直す（open）も、これで変える。"""

    type: Literal["update_annotation"] = "update_annotation"
    id: str
    body: str | None = Field(default=None, min_length=1)
    region_mm: Polygon | None = None
    about_task: Task | None = None
    status: Literal["open", "resolved"] | None = None

    ai_may_submit = True

    async def scope(self, session, work):
        item = await get_in_work(session, AnnotationItem, self.id, work.id)
        return Scope("can_comment", work_obj(work.id), [("page", item.page_id)])

    async def apply(self, ctx):
        item = await ctx.session.get(AnnotationItem, self.id)
        changes = self.model_dump(exclude={"type", "id"}, exclude_unset=True, mode="json")
        if not changes:
            raise Invalid("変える項目がない")
        for k in ("body", "about_task", "status"):
            if k in changes and changes[k] is None:
                raise Invalid(f"{k} は空にできない")
        if "region_mm" in changes:
            changes["region_mm"] = _region(changes["region_mm"])
        rc = RowChanges(ctx)
        rc.change_or_hold(item, changes, item.page_id)
        return rc.inverse([item.page_id], "赤入れを直した取り消し")


class RecordAnnotationJob(OpBase):
    """赤入れから作った依頼を、その赤入れに残す（http_routes/annotation_routes.py が依頼を作った後に出す）。"""

    type: Literal["record_annotation_job"] = "record_annotation_job"
    id: str
    job_id: str

    async def scope(self, session, work):
        item = await get_in_work(session, AnnotationItem, self.id, work.id)
        return Scope("can_comment", work_obj(work.id), [("page", item.page_id)])

    async def apply(self, ctx):
        item = await ctx.session.get(AnnotationItem, self.id)
        await get_in_work(ctx.session, Job, self.job_id, ctx.work.id)
        if self.job_id in item.job_ids:
            raise Invalid("すでに残してある")
        rc = RowChanges(ctx)
        rc.set_plain(item, {"job_ids": [*item.job_ids, self.job_id]})
        return rc.inverse([item.page_id], "赤入れの依頼の記録の取り消し")
