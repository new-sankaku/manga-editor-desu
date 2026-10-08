"""巻・話・ページ・コマを足す・変える・抜く操作。"""


from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.material_and_setting_tables import MaterialEntry
from v3server.canonical_tables.page_item_tables import AnnotationItem, PageItem, PanelTemplate
from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.text_and_layer_tables import PanelLayer, TextItem
from v3server.canonical_tables.work_tree_tables import Episode, Page, Panel, Volume
from v3server.name_structure.image_placement import ImagePlacement
from v3server.name_structure.item_styles import FrameStyle, checked_adjustments
from v3server.name_structure.name_draft_schema import PanelFrame
from v3server.openfga_permissions import Tuple
from v3server.operations.ai_involvement import ROW_ACTION, ROW_TASK, field_task, require_actor_may
from v3server.operations.human_hand_guard import (
    change_with_human_hand,
    page_id_of,
    refuse_if_fixed,
    remove_or_hold,
)
from v3server.operations.operation_base import (
    OpBase,
    Scope,
    _changed,
    get_in_work,
    page_obj,
    work_obj,
)
from v3server.v3_error_types import HumanHandProtected, Invalid


def _frame_dict(v: dict[str, Any] | None) -> dict[str, Any]:
    """枠は人が描いても計算で決めても同じ形（PanelFrame）。空の辞書（None も）は「枠がまだ無い」。
    四角でない形・斜めの枠も、多角形の頂点で持つ。"""
    if not v:
        return {}
    return PanelFrame.model_validate(v).model_dump(mode="json")


async def validated_placement(session, work_id: str, placement: dict[str, Any] | None, image_id: str | None):
    """絵の切り抜きと置き場を確かめる。絵が決まっていなければ置けない。切り抜きは絵の大きさの中。"""
    if placement is None:
        return None
    if image_id is None:
        raise Invalid("絵が決まっていないので、切り抜きと置き場を決められない")
    pl = ImagePlacement.model_validate(placement)
    img = await get_in_work(session, ImageFile, image_id, work_id)
    if not pl.fits_image(img.width, img.height):
        raise Invalid(f"切り抜き {pl.crop_px} が絵の大きさ {img.width}x{img.height} の外に出ている")
    return pl.model_dump(mode="json")


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

    ai_may_submit = True

    @field_validator("frame")
    @classmethod
    def _frame(cls, v):
        return _frame_dict(v)

    async def scope(self, session, work):
        await get_in_work(session, Page, self.page_id, work.id)
        return Scope("can_draw", page_obj(self.page_id), [("page", self.page_id)])

    async def apply(self, ctx):
        require_actor_may(ctx.actor, ctx.work, ROW_TASK["panels"], "decide")
        # 人が足したコマは、足した項目に人の手の印を付ける（人が描いた枠をAIが割り直さないように）
        marks = sorted(k for k in ("order", "frame", "role", "content") if getattr(self, k)) \
            if ctx.actor.kind == "human" else []
        ctx.session.add(
            Panel(
                id=self.id,
                work_id=ctx.work.id,
                page_id=self.page_id,
                order=self.order,
                frame=self.frame,
                role=self.role,
                content=self.content,
                human_hand_fields=marks,
            )
        )
        return {"type": "set_removed", "target_kind": "panel", "id": self.id, "removed": True}


class UpdatePanel(OpBase):
    """コマを変える。人が変えた項目には人の手の印が付く。AIの変更が人の手の所に当たると判断待ちに置く（human_hand_guard.py）。"""

    type: Literal["update_panel"] = "update_panel"
    id: str
    order: int | None = None
    frame: dict[str, Any] | None = None
    role: str | None = None
    content: dict[str, Any] | None = None
    image_id: str | None = None
    # 絵の切り抜きと置き場（ImagePlacement）。None を渡すと置き場を決めていない状態に戻す
    image_placement: dict[str, Any] | None = None
    human_confirmed: bool | None = None
    # 枠の線と塗り（name_structure/item_styles.py の FrameStyle）。None は作品の設定（preferences.frame_style）に従う
    frame_style: dict[str, Any] | None = None
    # 仕上げ（コマの絵全体に掛ける）
    adjustments: list[dict[str, Any]] | None = None
    # 人の手の印をこの値にする。人だけが渡せる（取り消しで元に戻すときと、人が印を外すとき）
    human_hand_fields: list[str] | None = None

    ai_may_submit = True

    @field_validator("frame_style")
    @classmethod
    def _frame_style(cls, v):
        return None if v is None else FrameStyle.model_validate(v).model_dump(mode="json")

    @field_validator("frame")
    @classmethod
    def _frame(cls, v):
        return _frame_dict(v)

    async def scope(self, session, work):
        panel = await get_in_work(session, Panel, self.id, work.id)
        return Scope("can_draw", page_obj(panel.page_id), [("page", panel.page_id), ("panel", panel.id)])

    async def apply(self, ctx):
        panel = await ctx.session.get(Panel, self.id)
        changes = self.model_dump(exclude={"type", "id", "human_hand_fields"}, exclude_unset=True)
        if not changes and self.human_hand_fields is None:
            raise Invalid("変える項目がない")
        if "human_confirmed" in changes and ctx.actor.kind == "ai":
            raise HumanHandProtected("人の確定印を変えられるのは人だけ")
        if "adjustments" in changes:
            if changes["adjustments"] is None:
                raise Invalid("adjustments は空にできない（外すときは []）")
            changes["adjustments"] = checked_adjustments(changes["adjustments"])
        if "image_id" in changes and changes["image_id"] is not None:
            await get_in_work(ctx.session, ImageFile, changes["image_id"], ctx.work.id)
        if "image_placement" in changes:
            changes["image_placement"] = await validated_placement(
                ctx.session, ctx.work.id, changes["image_placement"], changes.get("image_id", panel.image_id))
        before = change_with_human_hand(ctx, panel, changes, self.human_hand_fields)
        return {"type": self.type, "id": self.id, **before}


class UpdatePage(OpBase):
    """ページの段の割りを変える。人が引いた割りも、AIが決めた割りも同じ形（name_structure の NamePage の rows など）。"""

    type: Literal["update_page"] = "update_page"
    id: str
    layout: dict[str, Any] | None = None
    human_hand_fields: list[str] | None = None

    ai_may_submit = True

    async def scope(self, session, work):
        await get_in_work(session, Page, self.id, work.id)
        return Scope("can_draw", page_obj(self.id), [("page", self.id)])

    async def apply(self, ctx):
        page = await ctx.session.get(Page, self.id)
        changes = self.model_dump(exclude={"type", "id", "human_hand_fields"}, exclude_unset=True)
        if not changes and self.human_hand_fields is None:
            raise Invalid("変える項目がない")
        before = change_with_human_hand(ctx, page, changes, self.human_hand_fields)
        return {"type": self.type, "id": self.id, **before}


# ---------------------------------------------------------------- 抜く・戻す


_REMOVABLE = {"volume": Volume, "episode": Episode, "page": Page, "panel": Panel, "text_item": TextItem,
              "panel_layer": PanelLayer, "page_item": PageItem, "annotation": AnnotationItem,
              "material_entry": MaterialEntry, "panel_template": PanelTemplate}


class SetRemoved(OpBase):
    """巻・話・ページ・コマ・文字・層・トーンと図形・赤入れ・設定資料・コマの型を抜く・戻す。
    消さない（ごみ箱。V3細部の決めごと 18章）。「動かさない」の付いた行は人も抜けない。"""

    type: Literal["set_removed"] = "set_removed"
    target_kind: Literal["volume", "episode", "page", "panel", "text_item", "panel_layer", "page_item", "annotation",
                         "material_entry", "panel_template"]
    id: str
    removed: bool

    ai_may_submit = True

    async def scope(self, session, work):
        obj = await get_in_work(session, _REMOVABLE[self.target_kind], self.id, work.id)
        if self.target_kind == "panel":
            return Scope("can_draw", page_obj(obj.page_id), [("page", obj.page_id), ("panel", obj.id)])
        if self.target_kind in ("text_item", "panel_layer", "page_item"):
            locks = [("page", obj.page_id), ("item", obj.id)] + ([("panel", obj.panel_id)] if obj.panel_id else [])
            return Scope("can_draw", page_obj(obj.page_id), locks)
        if self.target_kind == "annotation":
            return Scope("can_comment", work_obj(work.id), [("page", obj.page_id)])
        if self.target_kind == "page":
            return Scope("can_manage", work_obj(work.id), [("page", obj.id)], page_tree=obj.id)
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        obj = await ctx.session.get(_REMOVABLE[self.target_kind], self.id)
        refuse_if_fixed(obj)
        if ctx.actor.kind == "ai":
            if self.target_kind in ("volume", "episode", "panel_template"):
                raise HumanHandProtected("巻・話・コマの型を抜く・戻すのは人だけ")
            task = ROW_TASK[obj.__tablename__]
            require_actor_may(ctx.actor, ctx.work, field_task(obj, task), ROW_ACTION.get(obj.__tablename__, "decide"))
        if obj.removed == self.removed:
            raise Invalid("すでにその状態")
        # 人の手の印か確定印の付いた行にAIが当たったら、抜かずに判断待ちに置く（human_hand_guard.py）
        if not remove_or_hold(ctx, obj, self.removed):
            # 何も変えていない。取り消すと、置いた判断待ちを下げるだけになる（窓口が包む）
            return {"type": "restore_rows", "label": "抜く・戻すを判断待ちにした取り消し",
                    "page_ids": [p for p in [page_id_of(obj)] if p], "snapshot": {obj.__tablename__: {}}}
        return {**self.model_dump(), "removed": not self.removed}


def _jsonable(v):
    return v.isoformat() if isinstance(v, datetime) else v
