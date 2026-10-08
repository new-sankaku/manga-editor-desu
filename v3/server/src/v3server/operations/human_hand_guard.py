"""人の手の印（V3細部の決めごと 10.2、V3ハーネス設計 9.2）。ページ・コマ・文字・層の項目を変える操作は、必ずここを通して変える。

- 人が変えた項目には、人の手の印を付ける（項目ごと）
- 人の手の印を外せるのは人だけ（human_hand_fields を明示して渡す）
- AIが変えるときは、その項目の作業のAIの関与も確かめる（ai_involvement.py）
- AIの変更が、人の手の印の付いた項目か人の確定印の付いたコマに当たったときは、断らずにその項目を判断待ち（HeldAiChange）に置き、
  印の無い項目はそのまま当てる（change_with_human_hand）。どの操作も同じ。AIの案を人が採用したときも同じ（ai_change=True）
- AIが人の手の印・確定印の付いた行を抜く・戻すときも、判断待ちに置く（remove_or_hold）
- 行ごと動かすAIの操作（コマを分ける・合わせるなど）が人の手の所に当たったときは、操作ごと判断待ちに置く（hold_ai_operation）
- 置いた判断待ちは ctx.held_changes に積む。窓口（operation_submit_and_undo.submit）がそれを出来事に残して呼んだ側に返し、
  取り消すとまだ決めていない判断待ちを下げる（held_change_operations.UndoWithHeldChanges）

- 人が掛けた「動かさない」（fixed）の付いた行は、人もAIも変えられない（FixedByPerson）。外すのは SetFixed（人だけ）

どの項目に印を付けるか、どの作業に入るかは ai_involvement.HUMAN_EDITABLE_FIELDS の1か所で決める。
"""

import json
from typing import Any

from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.text_and_layer_tables import HeldAiChange
from v3server.operations.ai_involvement import (
    HUMAN_EDITABLE_FIELDS,
    require_ai_may_change_fields,
)
from v3server.v3_error_types import FixedByPerson, HumanHandProtected


def hand_fields_of(obj) -> frozenset[str]:
    return frozenset(HUMAN_EDITABLE_FIELDS[obj.__tablename__])


def is_human_held(obj) -> bool:
    """人の手の印か確定印が1つでも付いているか（AIが行ごと抜けるか）。"""
    return bool(obj.human_hand_fields) or bool(getattr(obj, "human_confirmed", False))


def refuse_if_fixed(obj) -> None:
    """人が「動かさない」を掛けた行は、誰も変えられない。"""
    if getattr(obj, "fixed", False):
        raise FixedByPerson(f"{obj.__tablename__}:{obj.id} は人が「動かさない」にしている。先に人が外す")


def touches_human_hand(obj, fields: set[str]) -> bool:
    """AIがこの行のこの項目を変えると、人の手の所に当たるか（行ごと動かす操作が、判断待ちにするかを決める）。"""
    return getattr(obj, "human_confirmed", False) or bool(set(obj.human_hand_fields) & fields)


def json_value(v: Any) -> Any:
    """比べるための JSON の値（tuple と list、0 と 0.0 の違いを消す）。"""
    return json.loads(json.dumps(v, default=str))


def _canon(field: str, v: Any) -> Any:
    v = json_value(v)
    if field in ("content", "layout") and isinstance(v, dict):
        # 辞書の中の None は未定。キーが無いのと同じに扱う
        return {k: x for k, x in v.items() if x is not None}
    return v


def drop_unchanged(obj, changes: dict[str, Any]) -> dict[str, Any]:
    """今の値と同じ項目を除く。同じ値を書いても「触った」ことにしない（人の手の印を外さない・判断待ちを作らない）。"""
    return {k: v for k, v in changes.items() if _canon(k, getattr(obj, k)) != _canon(k, v)}


def page_id_of(obj) -> str | None:
    """判断待ちに残すページ（ロックと権限の範囲）。ページに属さない行（設定資料・企画）は None。"""
    return obj.id if obj.__tablename__ == "pages" else getattr(obj, "page_id", None)


def split_held_changes(obj, changes: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """(当ててよい変更, 人の手の所に当たる変更)。確定印の付いたコマは全部の項目が当たる。"""
    if getattr(obj, "human_confirmed", False):
        return {}, dict(changes)
    marked = set(obj.human_hand_fields)
    return ({k: v for k, v in changes.items() if k not in marked},
            {k: v for k, v in changes.items() if k in marked})


def _held_row(ctx, row: HeldAiChange) -> str:
    ctx.session.add(row)
    ctx.held_changes.append({"id": row.id, "target_table": row.target_table, "target_id": row.target_id,
                             "field": row.field, "kind": row.kind, "proposal_id": row.proposal_id})
    return row.id


def hold_ai_changes(ctx, obj, held: dict[str, Any], proposal_id: str | None = None,
                    page_id: str | None = None) -> list[str]:
    """人の手の所に当たったAIの変更を、項目ごとに判断待ちに置き、置いた行の id を返す。"""
    page_id = page_id_of(obj) if page_id is None else page_id
    return [_held_row(ctx, HeldAiChange(
        id=new_id(), work_id=ctx.work.id, target_table=obj.__tablename__, target_id=obj.id, page_id=page_id,
        field=field, proposed_value=json_value(value),
        current_value=json_value(getattr(obj, field)), proposal_id=proposal_id, status="open"))
        for field, value in sorted(held.items())]


def change_with_human_hand(ctx, obj, changes: dict[str, Any], explicit_hand_fields: list[str] | None = None,
                           mark_as_human: bool | None = None, *, ai_change: bool | None = None,
                           proposal_id: str | None = None, page_id: str | None = None) -> dict[str, Any]:
    """changes を当て、当てた項目の元の値（人の手の印も含む）を返す。返した値を同じ操作で流せば元に戻る。

    explicit_hand_fields: 人の手の印をこの値にする（取り消しで元に戻すときと、人が印を外すとき）。AIは渡せない。
    mark_as_human: 変えた項目に人の手の印を付けるか。None なら操作した者で決める（人なら付ける、AIなら外す）。
    ai_change: AIの変更として扱うか。None なら操作した者で決める。AIの案を人が採用するときは True。
      AIの変更が人の手の印の付いた項目に当たると、その項目は書かずに判断待ちに置き（ctx.held_changes に積む）、
      残りの項目を当てる。今と同じ値は「変えた」ことにしない（印を外さない・判断待ちを作らない）。
    proposal_id・page_id: 判断待ちに残す、元の案とページ（page_id は無ければ行から決める）。
    """
    actor = ctx.actor
    if explicit_hand_fields is not None and actor.kind == "ai":
        raise HumanHandProtected("人の手の印を変えられるのは人だけ")
    if ai_change is None:
        ai_change = actor.kind == "ai"
    if ai_change:
        changes = drop_unchanged(obj, changes)
    if changes:
        refuse_if_fixed(obj)
    if ai_change:
        changes, held = split_held_changes(obj, changes)
        if held:
            hold_ai_changes(ctx, obj, held, proposal_id, page_id)
    require_ai_may_change_fields(actor, ctx.work, obj.__tablename__, set(changes), obj)
    before = {k: getattr(obj, k) for k in changes}
    before["human_hand_fields"] = list(obj.human_hand_fields)
    for k, v in changes.items():
        setattr(obj, k, v)
    if explicit_hand_fields is not None:
        obj.human_hand_fields = sorted(set(explicit_hand_fields))
        return before
    touched = set(changes) & hand_fields_of(obj)
    human = (actor.kind == "human") if mark_as_human is None else mark_as_human
    marks = set(obj.human_hand_fields)
    obj.human_hand_fields = sorted(marks | touched if human else marks - touched)
    return before


def remove_or_hold(ctx, obj, removed: bool, *, ai_change: bool | None = None, proposal_id: str | None = None,
                   page_id: str | None = None) -> bool:
    """行を抜く・戻す。AIが人の手の印か確定印の付いた行に当たったときは、変えずに判断待ち（項目 removed）に置き、
    False を返す。当てたら True。「動かさない」の付いた行は誰も変えられない。"""
    refuse_if_fixed(obj)
    if ai_change is None:
        ai_change = ctx.actor.kind == "ai"
    if ai_change and is_human_held(obj):
        hold_ai_changes(ctx, obj, {"removed": removed}, proposal_id, page_id)
        return False
    obj.removed = removed
    return True


def hold_ai_operation(ctx, op: dict[str, Any], target, page_id: str | None, reason: str) -> str:
    """行ごと動かすAIの操作（コマを分ける・合わせるなど）が人の手の所に当たったとき、操作ごと判断待ちに置く。
    人が採ると、同じ操作を人の操作として当てる（held_change_operations.py）。"""
    return _held_row(ctx, HeldAiChange(
        id=new_id(), work_id=ctx.work.id, target_table=target.__tablename__, target_id=target.id, page_id=page_id,
        field=op["type"], proposed_value=None, current_value=None, proposal_id=None, status="open",
        kind="ai_operation", choices=["accept", "reject"], payload={"op": json_value(op), "reason": reason}))


def inverse_with_held(ctx, inverse: dict[str, Any] | None) -> dict[str, Any] | None:
    """この操作で置いた判断待ちを、取り消すときに下げるよう、取り消しの操作を包む（窓口が呼ぶ）。
    案の採用で置いた判断待ち（proposal_id あり）は、案の取り消し（restore_name_snapshot）が下げるので包まない。
    包まずに下げると、やり直し（案をもう一度採用する）で判断待ちが新しく作られ、戻した分と重なるため。"""
    ids = [h["id"] for h in ctx.held_changes if h["proposal_id"] is None]
    if inverse is None or not ids:
        return inverse
    return {"type": "undo_with_held_changes", "undo": inverse, "withdraw": ids}
