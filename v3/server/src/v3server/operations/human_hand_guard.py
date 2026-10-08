"""人の手の印（V3細部の決めごと 10.2、V3ハーネス設計 9.2）。ページ・コマ・文字・層の項目を変える操作は、必ずここを通して変える。

- 人が変えた項目には、人の手の印を付ける（項目ごと）
- AIは、人の手の印の付いた項目と、人の確定印の付いたコマを変えられない（HumanHandProtected）
- 人の手の印を外せるのは人だけ（human_hand_fields を明示して渡す）
- AIが変えるときは、その項目の作業のAIの関与も確かめる（ai_involvement.py）
- AIの案が人の手の所を変えようとしたときは、黙って捨てずに判断待ち（HeldAiChange）に置く（split_ai_proposal_changes）

- 人が掛けた「動かさない」（fixed）の付いた行は、人もAIも変えられない（FixedByPerson）。外すのは SetFixed（人だけ）
- この後に足した操作は、AIが人の手の所に当たったとき断らずに判断待ちに置く（change_or_hold・hold_ai_operation）

どの項目に印を付けるか、どの作業に入るかは ai_involvement.HUMAN_EDITABLE_FIELDS の1か所で決める。
"""

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.text_and_layer_tables import HeldAiChange
from v3server.canonical_tables.work_tree_tables import Work
from v3server.operations.ai_involvement import (
    HUMAN_EDITABLE_FIELDS,
    require_ai_may_change_fields,
)
from v3server.request_actor import Actor
from v3server.v3_error_types import FixedByPerson, HumanHandProtected


def hand_fields_of(obj) -> frozenset[str]:
    return frozenset(HUMAN_EDITABLE_FIELDS[obj.__tablename__])


def is_human_held(obj) -> bool:
    """人の手の印か確定印が1つでも付いているか（AIが行ごと抜けるか）。"""
    return bool(obj.human_hand_fields) or bool(getattr(obj, "human_confirmed", False))


def refuse_if_ai_touches_human_hand(actor: Actor, obj, fields: set[str]) -> None:
    """AIが人の手の所を変えようとしていれば止める。"""
    if actor.kind != "ai":
        return
    if getattr(obj, "human_confirmed", False):
        raise HumanHandProtected(f"{obj.__tablename__}:{obj.id} は人の確定印が付いている")
    hit = sorted(set(obj.human_hand_fields) & fields)
    if hit:
        raise HumanHandProtected(f"{obj.__tablename__}:{obj.id} の {', '.join(hit)} は人の手の印が付いている")


def refuse_if_ai_removes_human_hand(actor: Actor, obj) -> None:
    refuse_if_fixed(obj)
    if actor.kind == "ai" and is_human_held(obj):
        raise HumanHandProtected(f"{obj.__tablename__}:{obj.id} は人の手の印が付いている")


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


def split_ai_proposal_changes(obj, changes: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """AIが作った案を当てるときに使う。(当ててよい変更, 人の手の所に当たる変更) を返す。
    当たる変更は呼ぶ側が hold_ai_changes で判断待ちに置く。採用したのが人でも、AIの案である限り同じ。"""
    if getattr(obj, "human_confirmed", False):
        return {}, dict(changes)
    marked = set(obj.human_hand_fields)
    return ({k: v for k, v in changes.items() if k not in marked},
            {k: v for k, v in changes.items() if k in marked})


def hold_ai_changes(session: AsyncSession, work_id: str, obj, page_id: str, held: dict[str, Any],
                    proposal_id: str | None) -> list[str]:
    """人の手の所に当たったAIの変更を判断待ちに置き、置いた行の id を返す。"""
    ids = []
    for field, value in sorted(held.items()):
        row = HeldAiChange(id=new_id(), work_id=work_id, target_table=obj.__tablename__, target_id=obj.id, page_id=page_id,
                           field=field, proposed_value=json_value(value), current_value=json_value(getattr(obj, field)),
                           proposal_id=proposal_id, status="open")
        session.add(row)
        ids.append(row.id)
    return ids


def change_with_human_hand(actor: Actor, obj, changes: dict[str, Any], explicit_hand_fields: list[str] | None = None,
                           mark_as_human: bool | None = None, *, work: Work) -> dict[str, Any]:
    """changes を当て、元の値（人の手の印も含む）を返す。返した値を同じ操作で流せば元に戻る。

    explicit_hand_fields: 人の手の印をこの値にする（取り消しで元に戻すときと、人が印を外すとき）。AIは渡せない。
    mark_as_human: 変えた項目に人の手の印を付けるか。None なら操作した者で決める（人なら付ける、AIなら外す）。
    work: AIが変えるときに、項目の作業のAIの関与を確かめるため。
    """
    if explicit_hand_fields is not None and actor.kind == "ai":
        raise HumanHandProtected("人の手の印を変えられるのは人だけ")
    if changes:
        refuse_if_fixed(obj)
    refuse_if_ai_touches_human_hand(actor, obj, set(changes))
    require_ai_may_change_fields(actor, work, obj.__tablename__, set(changes), obj)
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


def change_or_hold(ctx, obj, changes: dict[str, Any], page_id: str | None,
                   explicit_hand_fields: list[str] | None = None) -> tuple[dict[str, Any], list[str]]:
    """change_with_human_hand と同じ。ただしAIが人の手の所に当たったときは断らず、その項目を判断待ちに置き、
    残りを当てる。(元の値, 置いた判断待ちの id) を返す。人の操作はそのまま当てる。"""
    if ctx.actor.kind != "ai":
        return change_with_human_hand(ctx.actor, obj, changes, explicit_hand_fields, work=ctx.work), []
    changes = drop_unchanged(obj, changes)
    if changes:
        refuse_if_fixed(obj)
    free, held = split_ai_proposal_changes(obj, changes)
    held_ids = hold_ai_changes(ctx.session, ctx.work.id, obj, page_id, held, None) if held else []
    before = change_with_human_hand(ctx.actor, obj, free, explicit_hand_fields, work=ctx.work)
    return before, held_ids


def hold_ai_operation(ctx, op: dict[str, Any], target, page_id: str | None, reason: str) -> str:
    """行ごと動かすAIの操作（コマを分ける・合わせるなど）が人の手の所に当たったとき、操作ごと判断待ちに置く。
    人が採ると、同じ操作を人の操作として当てる（held_change_operations.py）。"""
    row = HeldAiChange(id=new_id(), work_id=ctx.work.id, target_table=target.__tablename__, target_id=target.id,
                       page_id=page_id, field=op["type"], proposed_value=None, current_value=None, proposal_id=None,
                       status="open", kind="ai_operation", choices=["accept", "reject"],
                       payload={"op": json_value(op), "reason": reason})
    ctx.session.add(row)
    return row.id
