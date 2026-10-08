"""文字（吹き出し・ナレーションの箱・描き文字）と、コマの絵の層を、足す・変える操作。抜く・戻すは SetRemoved。

人もAIも同じ操作で変える。値の確かめ（種類・範囲）は誰が出しても同じ。
違うのは human_hand_guard.py の1か所だけ：人が変えた項目に人の手の印が付き、AIは印の付いた項目を変えられず、
AIが変えるときはその項目の作業のAIの関与を確かめる。
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.text_and_layer_tables import PanelLayer, TextItem
from v3server.canonical_tables.work_tree_tables import Panel
from v3server.name_structure.name_draft_schema import BalloonKind
from v3server.operations.ai_involvement import (
    ROW_TASK,
    require_actor_may,
    require_ai_may_change_fields,
)
from v3server.operations.human_hand_guard import change_with_human_hand
from v3server.operations.operation_base import OpBase, Scope, get_in_work, page_obj
from v3server.operations.work_tree_operations import validated_placement
from v3server.v3_error_types import Invalid

TextItemKind = Literal["balloon", "caption", "drawn_sfx"]
LayerRole = Literal["line_art", "solid_black", "tone", "color", "background", "effect", "text", "human_hand", "panel_art"]


class TextItemValues(BaseModel):
    """文字1つの値の形。足すときも変えるときも、変えた後の値をこの形で確かめる。"""

    model_config = ConfigDict(extra="ignore")

    item_kind: TextItemKind
    order: int = Field(ge=0)
    text: str
    speaker: str | None = None
    balloon_kind: BalloonKind | None = None
    writing_direction: Literal["vertical", "horizontal"] | None = None
    font_size_pt: float | None = Field(default=None, gt=0)
    box_mm: tuple[float, float, float, float] | None = None
    tail_target_mm: tuple[float, float] | None = None
    joined_to_previous: bool | None = None

    @model_validator(mode="after")
    def _consistent(self):
        if self.box_mm is not None and (self.box_mm[2] <= self.box_mm[0] or self.box_mm[3] <= self.box_mm[1]):
            raise ValueError(f"文字の箱の範囲が正しくない: {self.box_mm}")
        if self.item_kind == "drawn_sfx" and (self.balloon_kind is not None or self.speaker is not None):
            raise ValueError("描き文字には話者と吹き出しの種類が無い")
        if self.item_kind == "drawn_sfx" and self.tail_target_mm is not None:
            raise ValueError("描き文字にはしっぽが無い")
        return self


_TEXT_FIELDS = tuple(TextItemValues.model_fields)


def _check_text_values(values: dict[str, Any]) -> dict[str, Any]:
    try:
        return TextItemValues.model_validate(values).model_dump(mode="json")
    except ValueError as e:
        raise Invalid(f"文字の値が正しくない: {e}") from e


def _item_scope(page_id: str, panel_id: str, item_id: str) -> Scope:
    return Scope("can_draw", page_obj(page_id), [("page", page_id), ("panel", panel_id), ("item", item_id)])


class AddTextItem(OpBase):
    type: Literal["add_text_item"] = "add_text_item"
    id: str = Field(default_factory=new_id)
    panel_id: str
    item_kind: TextItemKind
    order: int
    text: str
    speaker: str | None = None
    balloon_kind: BalloonKind | None = None
    writing_direction: Literal["vertical", "horizontal"] | None = None
    font_size_pt: float | None = None
    box_mm: tuple[float, float, float, float] | None = None
    tail_target_mm: tuple[float, float] | None = None
    joined_to_previous: bool | None = None

    ai_may_submit = True

    async def scope(self, session, work):
        panel = await get_in_work(session, Panel, self.panel_id, work.id)
        return _item_scope(panel.page_id, panel.id, self.id)

    async def apply(self, ctx):
        panel = await ctx.session.get(Panel, self.panel_id)
        values = _check_text_values(self.model_dump(include=set(_TEXT_FIELDS)))
        set_fields = {k for k, v in values.items() if v is not None} | {"panel_id"}
        require_actor_may(ctx.actor, ctx.work, ROW_TASK["text_items"], "decide")
        require_ai_may_change_fields(ctx.actor, ctx.work, "text_items", set_fields)
        marks = sorted(set_fields) if ctx.actor.kind == "human" else []
        ctx.session.add(TextItem(id=self.id, work_id=ctx.work.id, page_id=panel.page_id, panel_id=panel.id,
                                 human_hand_fields=marks, removed=False, **values))
        return {"type": "set_removed", "target_kind": "text_item", "id": self.id, "removed": True}


class UpdateTextItem(OpBase):
    """文字を変える：文字・話者・種類・縦書きか横書きか・書体の大きさ・箱（動かす・大きさ）・しっぽの先・順・コマ。"""

    type: Literal["update_text_item"] = "update_text_item"
    id: str
    panel_id: str | None = None
    item_kind: TextItemKind | None = None
    order: int | None = None
    text: str | None = None
    speaker: str | None = None
    balloon_kind: BalloonKind | None = None
    writing_direction: Literal["vertical", "horizontal"] | None = None
    font_size_pt: float | None = None
    box_mm: tuple[float, float, float, float] | None = None
    tail_target_mm: tuple[float, float] | None = None
    joined_to_previous: bool | None = None
    human_hand_fields: list[str] | None = None

    ai_may_submit = True

    async def scope(self, session, work):
        item = await get_in_work(session, TextItem, self.id, work.id)
        return _item_scope(item.page_id, item.panel_id, item.id)

    async def apply(self, ctx):
        item = await ctx.session.get(TextItem, self.id)
        changes = self.model_dump(exclude={"type", "id", "human_hand_fields"}, exclude_unset=True, mode="json")
        if not changes and self.human_hand_fields is None:
            raise Invalid("変える項目がない")
        if "panel_id" in changes:
            panel = await get_in_work(ctx.session, Panel, changes["panel_id"], ctx.work.id)
            if panel.page_id != item.page_id:
                raise Invalid("文字を動かせるのは同じページのコマの間だけ")
        merged = {k: getattr(item, k) for k in _TEXT_FIELDS} | {k: v for k, v in changes.items() if k != "panel_id"}
        checked = _check_text_values(merged)
        changes = {k: checked.get(k, v) for k, v in changes.items()}
        before = change_with_human_hand(ctx.actor, item, changes, self.human_hand_fields, work=ctx.work)
        return {"type": self.type, "id": self.id, **before}


# ---------------------------------------------------------------- 層


class AddPanelLayer(OpBase):
    type: Literal["add_panel_layer"] = "add_panel_layer"
    id: str = Field(default_factory=new_id)
    panel_id: str
    role: LayerRole
    image_id: str | None = None
    stack_order: int
    visible: bool = True
    opacity: float = Field(default=1.0, ge=0, le=1)
    placement: dict[str, Any] | None = None

    ai_may_submit = True

    async def scope(self, session, work):
        panel = await get_in_work(session, Panel, self.panel_id, work.id)
        return _item_scope(panel.page_id, panel.id, self.id)

    async def apply(self, ctx):
        panel = await ctx.session.get(Panel, self.panel_id)
        if self.image_id is not None:
            await get_in_work(ctx.session, ImageFile, self.image_id, ctx.work.id)
        placement = await validated_placement(ctx.session, ctx.work.id, self.placement, self.image_id)
        require_actor_may(ctx.actor, ctx.work, ROW_TASK["panel_layers"], "decide")
        if ctx.actor.kind == "ai" and self.role == "human_hand":
            raise Invalid("人の手の層はAIが作れない")
        marks = ["image_id", "opacity", "placement", "role", "stack_order", "visible"] if ctx.actor.kind == "human" else []
        ctx.session.add(PanelLayer(id=self.id, work_id=ctx.work.id, page_id=panel.page_id, panel_id=panel.id,
                                   role=self.role, image_id=self.image_id, stack_order=self.stack_order,
                                   visible=self.visible, opacity=self.opacity, placement=placement,
                                   human_hand_fields=[m for m in marks if m != "placement" or placement is not None],
                                   removed=False))
        return {"type": "set_removed", "target_kind": "panel_layer", "id": self.id, "removed": True}


class UpdatePanelLayer(OpBase):
    """層を変える：絵を替える・重ねる順・見せるか・不透明度・切り抜きと置き場。"""

    type: Literal["update_panel_layer"] = "update_panel_layer"
    id: str
    role: LayerRole | None = None
    image_id: str | None = None
    stack_order: int | None = None
    visible: bool | None = None
    opacity: float | None = Field(default=None, ge=0, le=1)
    placement: dict[str, Any] | None = None
    human_hand_fields: list[str] | None = None

    ai_may_submit = True

    async def scope(self, session, work):
        layer = await get_in_work(session, PanelLayer, self.id, work.id)
        return _item_scope(layer.page_id, layer.panel_id, layer.id)

    async def apply(self, ctx):
        layer = await ctx.session.get(PanelLayer, self.id)
        changes = self.model_dump(exclude={"type", "id", "human_hand_fields"}, exclude_unset=True)
        if not changes and self.human_hand_fields is None:
            raise Invalid("変える項目がない")
        for k in ("role", "stack_order", "visible", "opacity"):
            if k in changes and changes[k] is None:
                raise Invalid(f"{k} は空にできない")
        if changes.get("image_id") is not None:
            await get_in_work(ctx.session, ImageFile, changes["image_id"], ctx.work.id)
        if "placement" in changes:
            changes["placement"] = await validated_placement(ctx.session, ctx.work.id, changes["placement"],
                                                             changes.get("image_id", layer.image_id))
        if ctx.actor.kind == "ai" and (layer.role == "human_hand" or changes.get("role") == "human_hand"):
            raise Invalid("人の手の層はAIが変えられない")
        before = change_with_human_hand(ctx.actor, layer, changes, self.human_hand_fields, work=ctx.work)
        return {"type": self.type, "id": self.id, **before}
