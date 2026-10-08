"""トーン・集中線・スピード線と、図形・絵記号（PageItem）を置く・変える操作。
人の「動かさない」（SetFixed）と、仕上げをまとめて外す（ResetAdjustments）も、ここに置く。

AIが人の手の印の付いた項目に当たったときは、断らずに判断待ちに置き、残りを当てる（RowChanges.change_or_hold）。
"""

from typing import Any, Literal

from pydantic import Field
from sqlalchemy import select

from v3server.canonical_tables.page_item_tables import PageItem
from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.text_and_layer_tables import PanelLayer, TextItem
from v3server.canonical_tables.work_tree_tables import Page, Panel
from v3server.name_structure.item_styles import ShapeSpec, ToneSpec, checked_adjustments
from v3server.name_structure.item_transform import ItemTransform
from v3server.operations.ai_involvement import (
    ROW_TASK,
    require_actor_may,
    require_ai_may_change_fields,
)
from v3server.operations.operation_base import OpBase, Scope, get_in_work, page_obj
from v3server.operations.row_snapshot import RowChanges
from v3server.v3_error_types import Invalid

PageItemKind = Literal["tone", "shape"]


def checked_spec(item_kind: str, spec: dict[str, Any]) -> dict[str, Any]:
    model = ToneSpec if item_kind == "tone" else ShapeSpec
    try:
        return model.model_validate(spec).model_dump(mode="json")
    except ValueError as e:
        raise Invalid(f"{item_kind} の中身が正しくない: {e}") from e


def checked_transform(t: dict[str, Any]) -> dict[str, Any]:
    try:
        return ItemTransform.model_validate(t).model_dump(mode="json")
    except ValueError as e:
        raise Invalid(f"置き方（回転・傾き・反転）が正しくない: {e}") from e


def checked_box(box: list[float] | tuple[float, ...]) -> list[float]:
    if len(box) != 4 or box[2] <= box[0] or box[3] <= box[1]:
        raise Invalid(f"箱の範囲が正しくない: {box}")
    return [float(v) for v in box]


async def _check_tone_target(session, work_id: str, page_id: str, panel_id: str | None, spec: dict[str, Any]) -> None:
    target = spec.get("target") or {}
    if target.get("kind") == "panel":
        panel = await get_in_work(session, Panel, target["panel_id"], work_id)
        if panel.page_id != page_id or (panel_id is not None and panel_id != panel.id):
            raise Invalid("トーンを貼るコマが、置くページ・コマと合わない")


def _item_scope(page_id: str, panel_id: str | None, item_id: str) -> Scope:
    locks = [("page", page_id), ("item", item_id)]
    if panel_id is not None:
        locks.append(("panel", panel_id))
    return Scope("can_draw", page_obj(page_id), locks)


class AddPageItem(OpBase):
    """トーン（網点・線・砂目・グラデ・雪・集中線・スピード線）か、図形・絵記号を置く。"""

    type: Literal["add_page_item"] = "add_page_item"
    id: str = Field(default_factory=new_id)
    page_id: str
    panel_id: str | None = None
    item_kind: PageItemKind
    spec: dict[str, Any]
    box_mm: tuple[float, float, float, float]
    transform: dict[str, Any] = Field(default_factory=dict)
    stack_order: int
    visible: bool = True
    opacity: float = Field(default=1.0, ge=0, le=1)
    adjustments: list[dict[str, Any]] = Field(default_factory=list)

    ai_may_submit = True

    async def scope(self, session, work):
        await get_in_work(session, Page, self.page_id, work.id)
        if self.panel_id is not None:
            panel = await get_in_work(session, Panel, self.panel_id, work.id)
            if panel.page_id != self.page_id:
                raise Invalid("コマとページが合わない")
        return _item_scope(self.page_id, self.panel_id, self.id)

    async def apply(self, ctx):
        spec = checked_spec(self.item_kind, self.spec)
        if self.item_kind == "tone":
            await _check_tone_target(ctx.session, ctx.work.id, self.page_id, self.panel_id, spec)
        values = {"spec": spec, "box_mm": checked_box(self.box_mm), "transform": checked_transform(self.transform),
                  "stack_order": self.stack_order, "visible": self.visible, "opacity": self.opacity,
                  "adjustments": checked_adjustments(self.adjustments)}
        require_actor_may(ctx.actor, ctx.work, ROW_TASK["page_items"], "decide")
        require_ai_may_change_fields(ctx.actor, ctx.work, "page_items", set(values))
        rc = RowChanges(ctx)
        rc.created(PageItem(id=self.id, work_id=ctx.work.id, page_id=self.page_id, panel_id=self.panel_id,
                            item_kind=self.item_kind, fixed=False, removed=False,
                            human_hand_fields=sorted(values) if ctx.actor.kind == "human" else [], **values))
        return rc.inverse([self.page_id], "トーン・図形を置いた取り消し")


class UpdatePageItem(OpBase):
    """トーン・図形を変える：中身・箱・置き方（回転・傾き・反転）・重ねる順・見せるか・不透明度・仕上げ・コマ。"""

    type: Literal["update_page_item"] = "update_page_item"
    id: str
    panel_id: str | None = None
    spec: dict[str, Any] | None = None
    box_mm: tuple[float, float, float, float] | None = None
    transform: dict[str, Any] | None = None
    stack_order: int | None = None
    visible: bool | None = None
    opacity: float | None = Field(default=None, ge=0, le=1)
    adjustments: list[dict[str, Any]] | None = None

    ai_may_submit = True

    async def scope(self, session, work):
        item = await get_in_work(session, PageItem, self.id, work.id)
        return _item_scope(item.page_id, item.panel_id, item.id)

    async def apply(self, ctx):
        item = await ctx.session.get(PageItem, self.id)
        changes = self.model_dump(exclude={"type", "id"}, exclude_unset=True, mode="json")
        if not changes:
            raise Invalid("変える項目がない")
        for k, v in changes.items():
            if v is None and k != "panel_id":
                raise Invalid(f"{k} は空にできない")
        if changes.get("panel_id") is not None:
            panel = await get_in_work(ctx.session, Panel, changes["panel_id"], ctx.work.id)
            if panel.page_id != item.page_id:
                raise Invalid("動かせるのは同じページのコマの間だけ")
        if "spec" in changes:
            changes["spec"] = checked_spec(item.item_kind, changes["spec"])
            if item.item_kind == "tone":
                await _check_tone_target(ctx.session, ctx.work.id, item.page_id,
                                         changes.get("panel_id", item.panel_id), changes["spec"])
        if "box_mm" in changes:
            changes["box_mm"] = checked_box(changes["box_mm"])
        if "transform" in changes:
            changes["transform"] = checked_transform(changes["transform"])
        if "adjustments" in changes:
            changes["adjustments"] = checked_adjustments(changes["adjustments"])
        rc = RowChanges(ctx)
        rc.change_or_hold(item, changes, item.page_id)
        return rc.inverse([item.page_id], "トーン・図形を変えた取り消し")


# ---------------------------------------------------------------- 動かさない・仕上げを外す

FIXABLE = {"panel": Panel, "text_item": TextItem, "panel_layer": PanelLayer, "page_item": PageItem}


async def _fixable_scope(session, work, target_kind: str, target_id: str) -> Scope:
    obj = await get_in_work(session, FIXABLE[target_kind], target_id, work.id)
    locks = [("page", obj.page_id)]
    if target_kind == "panel":
        locks.append(("panel", obj.id))
    else:
        locks.append(("item", obj.id))
    return Scope("can_draw", page_obj(obj.page_id), locks)


class SetFixed(OpBase):
    """人が「動かさない」を掛ける・外す。掛けた行は、人もAIも変えられない（外すまで）。AIは出せない。"""

    type: Literal["set_fixed"] = "set_fixed"
    target_kind: Literal["panel", "text_item", "panel_layer", "page_item"]
    id: str
    fixed: bool

    async def scope(self, session, work):
        return await _fixable_scope(session, work, self.target_kind, self.id)

    async def apply(self, ctx):
        obj = await ctx.session.get(FIXABLE[self.target_kind], self.id)
        if obj.fixed == self.fixed:
            raise Invalid("すでにその状態")
        obj.fixed = self.fixed
        return {**self.model_dump(), "fixed": not self.fixed}


class ResetAdjustments(OpBase):
    """仕上げ（白黒・明るさ・ぼかし・重ね方）をまとめて外す。1つの物か、ページの中の全部（target_kind=page）。
    「動かさない」の付いた物があれば、何も外さずに止める。"""

    type: Literal["reset_adjustments"] = "reset_adjustments"
    target_kind: Literal["page", "panel", "text_item", "panel_layer", "page_item"]
    id: str

    ai_may_submit = True

    async def scope(self, session, work):
        if self.target_kind == "page":
            await get_in_work(session, Page, self.id, work.id)
            return Scope("can_draw", page_obj(self.id), [("page", self.id)], page_tree=self.id)
        return await _fixable_scope(session, work, self.target_kind, self.id)

    async def apply(self, ctx):
        if self.target_kind == "page":
            objs = []
            for model in FIXABLE.values():
                objs += (await ctx.session.execute(
                    select(model).where(model.page_id == self.id, model.removed.is_(False)))).scalars().all()
            page_id = self.id
        else:
            obj = await ctx.session.get(FIXABLE[self.target_kind], self.id)
            objs, page_id = [obj], obj.page_id
        objs = [o for o in objs if o.adjustments]
        if not objs:
            raise Invalid("外す仕上げが無い")
        rc = RowChanges(ctx)
        for o in objs:
            rc.change_or_hold(o, {"adjustments": []}, page_id)
        return rc.inverse([page_id], "仕上げをまとめて外した取り消し")
