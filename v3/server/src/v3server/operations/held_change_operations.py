"""判断待ちのAIの変更（HeldAiChange）を、人が決める操作。

AIの案が人の手の印の付いた項目を変えようとしたとき、案を当てる操作（ApplyNameProposal）はその項目を書かずに判断待ちへ置く。
人が accept すると、その値を人の判断として書く（人の手の印が付く）。reject すると今の値のまま残す。
どちらも取り消せる（取り消すと判断待ちに戻り、accept で変えた値も元に戻る）。"""

from typing import Any, Literal

from v3server.canonical_tables.text_and_layer_tables import (
    HeldAiChange,
    PanelLayer,
    TextItem,
)
from v3server.canonical_tables.work_tree_tables import Page, Panel
from v3server.operations.human_hand_guard import change_with_human_hand
from v3server.operations.operation_base import OpBase, Scope, get_in_work, page_obj
from v3server.v3_error_types import HumanHandProtected, Invalid

HELD_TARGETS = {"pages": Page, "panels": Panel, "text_items": TextItem, "panel_layers": PanelLayer}


class ResolveHeldChange(OpBase):
    type: Literal["resolve_held_change"] = "resolve_held_change"
    id: str
    decision: Literal["accept", "reject", "reopen"]
    # reopen（取り消し）のときだけ：accept で変えた項目の元の値と、元の人の手の印
    restore: dict[str, Any] | None = None

    async def scope(self, session, work):
        held = await get_in_work(session, HeldAiChange, self.id, work.id)
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
        target = await ctx.session.get(HELD_TARGETS[held.target_table], held.target_id)
        if self.decision == "reopen":
            if held.status not in ("accepted", "rejected"):
                raise Invalid("決めていない判断待ちは戻せない")
            before_status = held.status
            if before_status == "accepted" and self.restore is not None:
                restore = dict(self.restore)
                marks = restore.pop("human_hand_fields")
                change_with_human_hand(ctx.actor, target, restore, marks, work=ctx.work)
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
            before = change_with_human_hand(ctx.actor, target, {held.field: held.proposed_value}, work=ctx.work)
        held.status = "accepted"
        return {"type": self.type, "id": self.id, "decision": "reopen", "restore": before}
