"""判断待ち（HeldAiChange）を、人が決める操作。

- field_change：AIの変更が人の手の印の付いた項目に当たった。accept でその値を人の判断として書く（人の手の印が付く）。
  reject は今の値のまま残す
- ai_operation：AIの操作（コマを分ける・合わせるなど）が人の手の所に当たった。accept でその操作を人の操作として当てる
- psd_*：人が直した PSD を戻したときに、そのまま当てられなかった層（psd_import_operations.py）。choices から選ぶ
  - psd_text_pixels：文字の層の画素が変わった。retype（アプリで打ち直す。params.text があればその文字にする）・
    adopt_as_image（画素を人の手の層としてコマに置き、文字を抜く）・discard（何もしない）
  - psd_unmatched_layer：どの物にも当たらない新しい層。add_as_layer（params.panel_id のコマに人の手の層として置く）・discard
  - psd_vector_changed：コマ枠・フキダシ・トーン・図形の層の画素が変わった（線や形の値には戻せない）。
    adopt_as_image（画素を人の手の層として置く。元の物は残す）・discard
  - psd_layer_missing：PSD から層が消えた。remove_item（その物を抜く）・keep
どれも取り消せる（取り消すと判断待ちに戻り、変えた値も元に戻る）。

UndoWithHeldChanges：AIの変更で判断待ちを置いた操作の取り消し。窓口が取り消しの操作を包む（human_hand_guard.inverse_with_held）。"""

from typing import Any, Literal

from pydantic import Field

from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.material_and_setting_tables import MaterialEntry, WorkPlan
from v3server.canonical_tables.page_item_tables import AnnotationItem, PageItem, PanelTemplate
from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.text_and_layer_tables import (
    HeldAiChange,
    PanelLayer,
    TextItem,
)
from v3server.canonical_tables.translation_review_import_tables import TextItemTranslation
from v3server.canonical_tables.work_tree_tables import Page, Panel
from sqlalchemy import select

from v3server.operations.human_hand_guard import change_with_human_hand
from v3server.operations.operation_base import OpBase, Scope, get_in_work, page_obj, work_obj
from v3server.v3_error_types import HumanHandProtected, Invalid

HELD_TARGETS = {"pages": Page, "panels": Panel, "text_items": TextItem, "panel_layers": PanelLayer,
                "page_items": PageItem, "annotation_items": AnnotationItem, "material_entries": MaterialEntry,
                "work_plans": WorkPlan, "panel_templates": PanelTemplate,
                "text_item_translations": TextItemTranslation}

# kind ごとの選べる手。何もしない手（reject・discard・keep）は値を変えない
CHOICES = {
    "ai_operation": ("accept", "reject"),
    "psd_text_pixels": ("retype", "adopt_as_image", "discard"),
    "psd_unmatched_layer": ("add_as_layer", "discard"),
    "psd_vector_changed": ("adopt_as_image", "discard"),
    "psd_layer_missing": ("remove_item", "keep"),
}
_NOTHING = {"reject", "discard", "keep"}


def _inner_op(held: HeldAiChange):
    # all_operation_types がこのファイルを読むので、ここで読む
    from v3server.operations.all_operation_types import op_adapter

    return op_adapter.validate_python(held.payload["op"])


async def _add_hand_layer(ctx, rc, panel_id: str, image_id: str, box_mm: list[float]) -> None:
    """PSD から取った画素を、コマの人の手の層として一番上に置く。"""
    panel = await get_in_work(ctx.session, Panel, panel_id, ctx.work.id)
    img = await get_in_work(ctx.session, ImageFile, image_id, ctx.work.id)
    layers = [la for la in (await ctx.session.execute(
        PanelLayer.__table__.select().where(PanelLayer.panel_id == panel.id, PanelLayer.removed.is_(False)))).all()]
    top = max((la.stack_order for la in layers), default=-1) + 1
    placement = {"crop_px": [0, 0, img.width, img.height], "dest_box_mm": list(box_mm)}
    rc.created(PanelLayer(id=new_id(), work_id=ctx.work.id, page_id=panel.page_id, panel_id=panel.id,
                          role="human_hand", image_id=img.id, stack_order=top, visible=True, opacity=1.0,
                          placement=placement, adjustments=[], fixed=False,
                          human_hand_fields=["image_id", "opacity", "placement", "role", "stack_order", "visible"],
                          removed=False))


class ResolveHeldChange(OpBase):
    type: Literal["resolve_held_change"] = "resolve_held_change"
    id: str
    decision: Literal["accept", "reject", "reopen", "choose"]
    # decision=choose のときの手（CHOICES）と、その手に要る値
    choice: str | None = None
    params: dict[str, Any] | None = None
    # reopen（取り消し）のときだけ：accept で変えた項目の元の値と、元の人の手の印（field_change）、
    # または当てた操作の取り消し（ほかの kind）
    restore: dict[str, Any] | None = None

    async def scope(self, session, work):
        held = await get_in_work(session, HeldAiChange, self.id, work.id)
        if held.kind == "ai_operation":
            # 採ると、その操作を人の操作として当てる。その操作と同じ権限・ロックで確かめる
            inner = await _inner_op(held).scope(session, work)
            return Scope(inner.relation, inner.object, inner.lock_targets, inner.page_tree)
        if held.target_table == "text_item_translations":
            # 訳文の判断待ちは、訳文を置ける人（作者・翻訳者）が決める。ロックは訳文を置く操作と同じ
            tr = await get_in_work(session, TextItemTranslation, held.target_id, work.id)
            return Scope("can_translate", work_obj(work.id), [("item", tr.text_item_id)])
        if held.page_id is None:
            return Scope("can_manage", work_obj(work.id))
        locks = [("page", held.page_id)]
        if held.target_table == "panels":
            locks.append(("panel", held.target_id))
        elif held.target_table in ("text_items", "panel_layers"):
            locks.append(("item", held.target_id))
        return Scope("can_draw", page_obj(held.page_id), locks)

    async def apply(self, ctx):
        if ctx.actor.kind != "human":
            raise HumanHandProtected("判断待ちを決めるのは人だけ")
        held = await ctx.session.get(HeldAiChange, self.id)
        if held.kind != "field_change":
            return await self._apply_choice(ctx, held)
        if self.decision == "choose":
            raise Invalid("field_change は accept か reject で決める")
        target = await ctx.session.get(HELD_TARGETS[held.target_table], held.target_id)
        if self.decision == "reopen":
            if held.status not in ("accepted", "rejected"):
                raise Invalid("決めていない判断待ちは戻せない")
            before_status = held.status
            if before_status == "accepted" and self.restore is not None:
                restore = dict(self.restore)
                marks = restore.pop("human_hand_fields")
                change_with_human_hand(ctx, target, restore, marks)
            held.status = "open"
            return {"type": self.type, "id": self.id, "decision": "accept" if before_status == "accepted" else "reject"}
        if held.status != "open":
            raise Invalid(f"判断待ちは {held.status}。決められるのは open だけ")
        if self.decision == "reject":
            held.status = "rejected"
            return {"type": self.type, "id": self.id, "decision": "reopen"}
        if held.field == "removed":
            before = {"removed": target.removed, "human_hand_fields": list(target.human_hand_fields)}
            target.removed = bool(held.proposed_value)
        else:
            before = change_with_human_hand(ctx, target, {held.field: held.proposed_value})
        held.status = "accepted"
        return {"type": self.type, "id": self.id, "decision": "reopen", "restore": before}

    async def _apply_choice(self, ctx, held: HeldAiChange):
        from v3server.operations.row_snapshot import RestoreRows, RowChanges

        if self.decision == "reopen":
            if held.status not in ("accepted", "rejected") or self.restore is None:
                raise Invalid("決めていない判断待ちは戻せない")
            undo = self.restore.get("undo")
            if undo is not None:
                if undo["type"] == "restore_rows":
                    await RestoreRows.model_validate(undo).apply(ctx)
                else:
                    from v3server.operations.all_operation_types import op_adapter

                    await op_adapter.validate_python(undo).apply(ctx)
            again = {"type": self.type, "id": self.id, "decision": "choose", "choice": held.chosen,
                     "params": self.restore.get("params")}
            held.status, held.chosen = "open", None
            return again
        if held.status != "open":
            raise Invalid(f"判断待ちは {held.status}。決められるのは open だけ")
        choice = {"accept": "accept", "reject": "reject"}.get(self.decision) if self.decision != "choose" else self.choice
        if choice not in CHOICES[held.kind]:
            raise Invalid(f"{held.kind} で選べる手は {CHOICES[held.kind]}")
        params = self.params or {}
        payload = held.payload or {}
        undo: dict[str, Any] | None = None
        if choice == "accept":
            undo = await _inner_op(held).apply(ctx)
        elif choice not in _NOTHING:
            rc = RowChanges(ctx)

            async def target():
                return await ctx.session.get(HELD_TARGETS[held.target_table], held.target_id)

            if choice == "retype":
                if "text" in params:
                    rc.change(await target(), {"text": params["text"]})
            elif choice in ("adopt_as_image", "add_as_layer"):
                panel_id = params.get("panel_id") or payload.get("panel_id")
                if panel_id is None:
                    raise Invalid("どのコマに置くか（params.panel_id）が要る")
                await _add_hand_layer(ctx, rc, panel_id, payload["image_id"], payload["box_mm"])
                if held.kind == "psd_text_pixels":
                    rc.remove(await target())
            elif choice == "remove_item":
                if payload.get("synthetic"):
                    raise Invalid("この層（紙・グループなど）は書き出しで作った物で、抜く物が無い。keep で閉じる")
                rc.remove(await target())
            undo = rc.inverse([held.page_id] if held.page_id else [], f"判断待ち {held.id} の取り消し")
        held.status = "rejected" if choice in _NOTHING else "accepted"
        held.chosen = choice
        return {"type": self.type, "id": self.id, "decision": "reopen", "restore": {"undo": undo, "params": self.params}}


class UndoWithHeldChanges(OpBase):
    """判断待ちを置いた操作の取り消し。中の取り消し（undo）を当て、withdraw のうちまだ決めていない判断待ちを下げる。
    これを取り消す（やり直す）ときは、下げた判断待ちを reopen で開き直す。決めた後の判断待ちは触らない。
    人の手の印を元に戻す操作を含むので、人だけが出せる。"""

    type: Literal["undo_with_held_changes"] = "undo_with_held_changes"
    undo: dict[str, Any]
    withdraw: list[str] = Field(default_factory=list)
    reopen: list[str] = Field(default_factory=list)

    def _inner(self):
        from v3server.operations.all_operation_types import op_adapter

        return op_adapter.validate_python(self.undo)

    async def scope(self, session, work):
        return await self._inner().scope(session, work)

    async def apply(self, ctx):
        rows = (await ctx.session.execute(select(HeldAiChange).where(
            HeldAiChange.id.in_(self.withdraw + self.reopen), HeldAiChange.work_id == ctx.work.id))).scalars().all()
        withdrawn, reopened = [], []
        for row in rows:
            if row.id in self.withdraw and row.status == "open":
                row.status = "withdrawn"
                withdrawn.append(row.id)
            elif row.id in self.reopen and row.status == "withdrawn":
                row.status = "open"
                reopened.append(row.id)
        inner_inverse = await self._inner().apply(ctx)
        if inner_inverse is None:
            return None
        return {"type": self.type, "undo": inner_inverse, "withdraw": sorted(reopened), "reopen": sorted(withdrawn)}
