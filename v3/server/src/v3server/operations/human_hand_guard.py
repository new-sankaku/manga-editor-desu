"""人の手の印（V3細部の決めごと 10.2、V3ハーネス設計 9.2）。ページとコマを変える操作は、必ずここを通して変える。

- 人が変えた項目には、人の手の印を付ける（項目ごと）
- AIは、人の手の印の付いた項目と、人の確定印の付いたコマを変えられない（HumanHandProtected）
- 人の手の印を外せるのは人だけ（human_hand_fields を明示して渡す）
"""

from typing import Any

from v3server.request_actor import Actor
from v3server.v3_error_types import HumanHandProtected

# 人の手の印を付ける項目。ここに無い項目（removed など）は印の対象にしない
PANEL_HAND_FIELDS = frozenset({"order", "frame", "role", "content", "image_id"})
PAGE_HAND_FIELDS = frozenset({"layout"})


def _hand_fields_of(obj) -> frozenset[str]:
    return PANEL_HAND_FIELDS if obj.__tablename__ == "panels" else PAGE_HAND_FIELDS


def refuse_if_ai_touches_human_hand(actor: Actor, obj, fields: set[str]) -> None:
    """AIが人の手の所を変えようとしていれば止める。"""
    if actor.kind != "ai":
        return
    if getattr(obj, "human_confirmed", False):
        raise HumanHandProtected(f"{obj.__tablename__}:{obj.id} は人の確定印が付いている")
    hit = sorted(set(obj.human_hand_fields) & fields)
    if hit:
        raise HumanHandProtected(f"{obj.__tablename__}:{obj.id} の {', '.join(hit)} は人の手の印が付いている")


def split_by_human_hand(actor: Actor, obj, changes: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """AIが案をまとめて書くときに使う。人の手の所を除いた変更と、除いた項目の名前を返す。
    人の操作なら全部をそのまま返す。"""
    if actor.kind != "ai":
        return changes, []
    if getattr(obj, "human_confirmed", False):
        return {}, sorted(changes)
    kept = sorted(set(obj.human_hand_fields) & set(changes))
    return {k: v for k, v in changes.items() if k not in kept}, kept


def change_with_human_hand(actor: Actor, obj, changes: dict[str, Any],
                           explicit_hand_fields: list[str] | None = None,
                           mark_as_human: bool | None = None) -> dict[str, Any]:
    """changes を当て、元の値（人の手の印も含む）を返す。返した値を同じ操作で流せば元に戻る。

    explicit_hand_fields: 人の手の印をこの値にする（取り消しで元に戻すときと、人が印を外すとき）。AIは渡せない。
    mark_as_human: 変えた項目に人の手の印を付けるか。None なら操作した者で決める（人なら付ける、AIなら外す）。
    """
    if explicit_hand_fields is not None and actor.kind == "ai":
        raise HumanHandProtected("人の手の印を変えられるのは人だけ")
    refuse_if_ai_touches_human_hand(actor, obj, set(changes))
    before = {k: getattr(obj, k) for k in changes}
    before["human_hand_fields"] = list(obj.human_hand_fields)
    for k, v in changes.items():
        setattr(obj, k, v)
    if explicit_hand_fields is not None:
        obj.human_hand_fields = sorted(set(explicit_hand_fields))
        return before
    touched = set(changes) & _hand_fields_of(obj)
    human = (actor.kind == "human") if mark_as_human is None else mark_as_human
    marks = set(obj.human_hand_fields)
    obj.human_hand_fields = sorted(marks | touched if human else marks - touched)
    return before
