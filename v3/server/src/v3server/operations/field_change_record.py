"""出来事ごとに、どの行のどの項目を、何から何に変えたかを残す（取り消しが後の変更を上書きしないため。点検1 8-1・点検5 4-1）。

操作の中身は見ず、SQLAlchemy の変更の記録（属性の履歴）から取る。操作の窓口（operation_submit_and_undo.submit）が
apply の間だけ記録し、出来事の field_changes に残す。操作ごとに書き足す物は無い。

形：{表: {行の id: {項目: {"before": 前の値, "after": 後の値}}}}
- 値は json_value で比べられる形にする
- 前の値が読み込まれていなかったときは "before" を置かない（分からない値を作らない）
- 行を足したとき：removed を持つ表は removed を True→False に変えたとして残す（取り消しで抜くのと同じ形）。
  removed を持たない表は、仮の項目 ROW_PRESENT を False→True として残す。消したときはその逆

取り消しのぶつかりの見方（find_undo_conflicts）
- 取り消しが戻す項目ごとに、今の値が「取り消す出来事の後の値」のままかを比べる。違えば、その項目を後で変えた出来事を挙げる
- 取り消す出来事が足した行を、取り消しで抜くとき：後の出来事を通して値が変わったままの項目があれば、ぶつかりにする
  （変えて戻した項目は数えない）
- NOT_COMPARED の項目は比べない。人の手の印（human_hand_fields）は、取り消す出来事が付けた・外した分だけを戻す
  （merge_hand_marks）。線の版（stroke_revision）は数え上げるだけで戻さない
"""

from contextlib import contextmanager
from typing import Any

from sqlalchemy import event as sa_event
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.event_and_lock_tables import Event
from v3server.canonical_tables.table_base import Base
from v3server.operations.human_hand_guard import json_value

ROW_PRESENT = "__row_present__"
NOT_COMPARED = frozenset({"human_hand_fields", "stroke_revision"})

FieldChanges = dict[str, dict[str, dict[str, dict[str, Any]]]]


def _row_key(obj) -> str:
    ident = inspect(obj).mapper.primary_key_from_instance(obj)
    return ":".join(str(v) for v in ident)


class FieldChangeRecorder:
    def __init__(self) -> None:
        self.changes: FieldChanges = {}

    def _put(self, obj, field: str, before: Any, after: Any, before_known: bool = True) -> None:
        row = self.changes.setdefault(obj.__tablename__, {}).setdefault(_row_key(obj), {})
        entry = row.get(field)
        if entry is None:
            entry = row[field] = {}
            if before_known:
                entry["before"] = json_value(before)
        entry["after"] = json_value(after)
        if "before" in entry and entry["before"] == entry["after"]:
            del row[field]
            if not row:
                del self.changes[obj.__tablename__][_row_key(obj)]

    def collect(self, session, flush_context=None) -> None:
        for obj in session.new:
            if not hasattr(obj, "__tablename__") or obj.__tablename__ == Event.__tablename__:
                continue
            if hasattr(obj, "removed"):
                self._put(obj, "removed", True, bool(obj.removed))
            else:
                self._put(obj, ROW_PRESENT, False, True)
        for obj in session.deleted:
            if hasattr(obj, "__tablename__"):
                self._put(obj, ROW_PRESENT, True, False)
        for obj in session.dirty:
            if not hasattr(obj, "__tablename__") or obj.__tablename__ == Event.__tablename__:
                continue
            state = inspect(obj)
            for attr in state.mapper.column_attrs:
                hist = state.attrs[attr.key].history
                if not hist.added and not hist.deleted:
                    continue
                after = hist.added[0] if hist.added else None
                if hist.deleted:
                    self._put(obj, attr.key, hist.deleted[0], after)
                else:
                    self._put(obj, attr.key, None, after, before_known=False)


@contextmanager
def record_field_changes(session: AsyncSession):
    """この中で行った変更を、flush のたびに集める。抜ける前に flush しておくこと。
    after_flush で集める（足した行の id は flush の中で決まるため。after_flush の時点では、行の一覧と属性の履歴は
    flush の前のまま残っている：SQLAlchemy の SessionEvents.after_flush の説明）。"""
    recorder = FieldChangeRecorder()
    sync = session.sync_session
    sa_event.listen(sync, "after_flush", recorder.collect)
    try:
        yield recorder
    finally:
        sa_event.remove(sync, "after_flush", recorder.collect)


def _touches(ev: Event, table: str, rid: str, field: str | None) -> bool:
    """出来事 ev が、その行のその項目（field が None なら、比べる項目のどれか）を変えたか。"""
    row = (ev.field_changes or {}).get(table, {}).get(rid)
    if row is None:
        return False
    if field is None:
        return any(f not in NOT_COMPARED for f in row)
    return field in row


def _net_changed_fields(later: list[Event], table: str, rid: str) -> set[str]:
    """後の出来事を通して、値が変わったままの項目（比べる項目だけ）。変えて戻した項目（取り消し・やり直し）は入れない。
    前の値が分からない項目は、変わったとみなす。"""
    first: dict[str, dict[str, Any]] = {}
    last: dict[str, Any] = {}
    for ev in later:
        for f, ch in ((ev.field_changes or {}).get(table, {}).get(rid) or {}).items():
            if f in NOT_COMPARED:
                continue
            first.setdefault(f, ch)
            last[f] = ch["after"]
    return {f for f, ch in first.items() if "before" not in ch or ch["before"] != last[f]}


def _event_summary(ev: Event) -> dict[str, Any]:
    return {"event_id": ev.id, "seq": ev.seq, "op_type": ev.op_type, "actor_kind": ev.actor_kind,
            "actor_id": ev.actor_id}


async def find_undo_conflicts(session: AsyncSession, undone: Event, undo_changes: FieldChanges) -> list[dict[str, Any]]:
    """取り消し（undo_changes）が、undone より後の出来事の変更を上書きする所。無ければ空。

    undone に記録が無い（この仕組みより前の出来事）ときは、ぶつかるかを確かめられないので呼ぶ側で止める。"""
    recorded = undone.field_changes or {}
    later: list[Event] | None = None
    out: list[dict[str, Any]] = []
    for table, rows in sorted(undo_changes.items()):
        for rid, fields in sorted(rows.items()):
            mine = recorded.get(table, {}).get(rid)
            if mine is None:
                continue
            created = mine.get("removed", {}).get("before") is True or mine.get(ROW_PRESENT, {}).get("before") is False
            for field, ch in sorted(fields.items()):
                if field in NOT_COMPARED:
                    continue
                removing_created = created and field in ("removed", ROW_PRESENT)
                if field not in mine and not removing_created:
                    continue
                still_after = field in mine and "before" in ch and ch["before"] == mine[field]["after"]
                if later is None:
                    later = list((await session.execute(
                        select(Event).where(Event.work_id == undone.work_id, Event.seq > undone.seq)
                        .order_by(Event.seq))).scalars())
                if removing_created:
                    changed = _net_changed_fields(later, table, rid)
                    if not changed and still_after:
                        continue
                    by = [e for e in later if any(_touches(e, table, rid, f) for f in changed)]
                else:
                    if still_after:
                        continue
                    by = [e for e in later if _touches(e, table, rid, field)]
                # 記録の無い後の出来事（この仕組みより前の操作）も、変えたかもしれないので挙げる。
                # ロックの出来事（取り消しの操作を持たない・正本の項目を変えない）は挙げない
                by += [e for e in later if e.field_changes is None and e.inverse is not None and e not in by]
                out.append({"table": table, "id": rid, "field": field,
                            "undone_after": mine[field]["after"] if field in mine else None,
                            "current": ch.get("before"), "events": [_event_summary(e) for e in by]})
    return out


def _model_of(table: str):
    for mapper in Base.registry.mappers:
        if getattr(mapper.class_, "__tablename__", None) == table:
            return mapper.class_
    raise KeyError(table)


async def merge_hand_marks(session: AsyncSession, undone: Event, recorder: FieldChangeRecorder) -> None:
    """取り消しが人の手の印を丸ごと前の値に戻したとき、取り消す出来事が付けた・外した分だけを戻し、
    後の出来事が付けた印は残す。"""
    recorded = undone.field_changes or {}
    for table, rows in recorder.changes.items():
        for rid, fields in rows.items():
            ch = fields.get("human_hand_fields")
            mine_row = recorded.get(table, {}).get(rid)
            if ch is None or mine_row is None or "before" not in ch:
                continue
            # 取り消す出来事がこの行の印を変えていなければ、戻す印は無い（今の印のまま）
            mine = mine_row.get("human_hand_fields", {"before": ch["before"], "after": ch["before"]})
            if "before" not in mine:
                continue
            added = set(mine["after"]) - set(mine["before"])
            dropped = set(mine["before"]) - set(mine["after"])
            merged = sorted((set(ch["before"]) - added) | dropped)
            if merged == ch["after"]:
                continue
            obj = await session.get(_model_of(table), rid)
            obj.human_hand_fields = merged
            ch["after"] = merged
