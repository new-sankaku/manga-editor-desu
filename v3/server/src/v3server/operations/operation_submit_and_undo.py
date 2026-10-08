"""操作の窓口。正本を変える唯一の入口（V3ハーネス設計 3章）。

1回の操作の流れ
1. 作品の行を FOR UPDATE で取る（作品ごとに書き込みは1本。V3ハーネス設計 9.3）
2. 権限を確かめる（AIは頼んだ人の権限）。AIが出せない操作（ai_may_submit が無い）はここで止める
3. ロックを確かめる
4. 正本を変え、出来事を1件追記する。変えた行と項目は出来事の field_changes に残す（field_change_record.py）。
   取り消しは、後の出来事が変えた項目を上書きするなら当てずに止め、記録する（undo_conflicts）。
   AIの変更が人の手の所に当たって判断待ちに置いた分は、出来事に残して返す（human_hand_guard.py）。
   取り消すと、まだ決めていない判断待ちを下げる
5. 権限の組（OpenFGA）を書き、確定する。確定に失敗したら書いた組を戻す
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.event_and_lock_tables import Event, Lock, UndoConflict
from v3server.canonical_tables.work_tree_tables import Work
from v3server.openfga_permissions import Authz
from v3server.operations.all_operation_types import op_adapter
from v3server.operations.field_change_record import find_undo_conflicts, merge_hand_marks, record_field_changes
from v3server.operations.human_hand_guard import inverse_with_held
from v3server.operations.operation_base import ApplyContext, OpBase, Scope
from v3server.request_actor import Actor
from v3server.v3_error_types import Forbidden, Invalid, Locked, NotFound, NotUndoable, UndoConflictError


async def lock_work(session: AsyncSession, work_id: str) -> Work:
    work = await session.get(Work, work_id, with_for_update=True)
    if work is None:
        raise NotFound(f"works:{work_id}")
    return work


def append_event(
    session: AsyncSession,
    work: Work,
    actor: Actor,
    op_type: str,
    payload: dict[str, Any],
    inverse: dict[str, Any] | None = None,
    undoes_event_id: str | None = None,
    held_changes: list[dict[str, Any]] | None = None,
    field_changes: dict[str, Any] | None = None,
) -> Event:
    """出来事を1件足す。呼ぶ前に lock_work で作品の行を取っておくこと。"""
    work.head_seq += 1
    event = Event(
        work_id=work.id,
        seq=work.head_seq,
        actor_kind=actor.kind,
        actor_id=actor.id,
        on_behalf_of=actor.on_behalf_of,
        op_type=op_type,
        payload=payload,
        inverse=inverse,
        undoes_event_id=undoes_event_id,
        held_changes=held_changes or None,
        field_changes=field_changes,
    )
    session.add(event)
    return event


async def conflicting_locks(
    session: AsyncSession, actor: Actor, targets: list[tuple[str, str]], page_tree: str | None = None
) -> list[Lock]:
    """他の者が持っていて期限内のロックのうち、targets のどれかに当たるもの。
    page_tree を渡すと、そのページの中のコマ・個別のロックも含める（ページ全体を変えるとき）。"""
    if not targets and page_tree is None:
        return []
    now = datetime.now(UTC)
    conds = [and_(Lock.target_kind == kind, Lock.target_id == t_id) for kind, t_id in targets]
    if page_tree is not None:
        conds.append(Lock.page_id == page_tree)
    locks = (await session.execute(select(Lock).where(or_(*conds), Lock.expires_at > now))).scalars().all()
    return [lock for lock in locks if not actor.holds(lock.holder_kind, lock.holder_id)]


def locked_error(lock: Lock) -> Locked:
    return Locked(
        f"{lock.target_kind}:{lock.target_id} は {lock.holder_kind}:{lock.holder_id} がロック中（{lock.reason}）"
    )


async def check_may_submit(session: AsyncSession, authz: Authz, actor: Actor, work: Work, op: OpBase) -> None:
    """op を出してよいか（AIが出せる操作か・権限・ロック）。submit が当てる前に確かめるのと同じもの。
    ファイルを置く口（絵のアップロード）は、ファイルを書く前にここで確かめる。"""
    if actor.kind == "ai" and not op.ai_may_submit:
        raise Forbidden(f"{op.type} はAIが出せない操作")
    await check_scope(session, authz, actor, await op.scope(session, work))


async def check_scope(session: AsyncSession, authz: Authz, actor: Actor, scope: Scope) -> None:
    if not await authz.check(actor.permission_user, scope.relation, scope.object):
        raise Forbidden(f"{actor.permission_user} に {scope.object} の {scope.relation} が無い")
    for lock in await conflicting_locks(session, actor, scope.lock_targets, scope.page_tree):
        raise locked_error(lock)


async def submit(
    session: AsyncSession,
    authz: Authz,
    actor: Actor,
    work_id: str,
    op: OpBase | dict[str, Any],
    undoes_event_id: str | None = None,
    *,
    commit: bool = True,
) -> Event:
    """commit=False：確定せずに flush までで返す。いくつもの操作と、ほかの行（依頼の状態など）を1回で確定するときに使う
    （generation_queue/service_call_activity.py）。権限の組（OpenFGA）を書く操作は確定と組を合わせられないので断る。"""
    if isinstance(op, dict):
        op = op_adapter.validate_python(op)
    try:
        work = await lock_work(session, work_id)
        undone: Event | None = None
        if undoes_event_id is not None:
            # 同じ出来事を2人が同時に取り消さないよう、作品の行を取ってから確かめる
            already = (
                await session.execute(select(Event.id).where(Event.undoes_event_id == undoes_event_id))
            ).first()
            if already is not None:
                raise NotUndoable("すでに取り消している")
            undone = await session.get(Event, undoes_event_id)
            if undone.field_changes is None:
                raise NotUndoable("この出来事には変えた項目の記録が無い（記録を始める前の出来事）。"
                                  "後の変更とぶつかるかを確かめられないので取り消さない")
        await check_may_submit(session, authz, actor, work, op)

        ctx = ApplyContext(session=session, work=work, actor=actor)
        with record_field_changes(session) as recorded:
            inverse = inverse_with_held(ctx, await op.apply(ctx))
            await session.flush()
        if undone is not None:
            conflicts = await find_undo_conflicts(session, undone, recorded.changes)
            if conflicts:
                raise UndoConflictError(_conflict_message(conflicts), conflicts)
            await merge_hand_marks(session, undone, recorded)
        if not commit and (ctx.tuple_writes or ctx.tuple_deletes):
            raise Invalid(f"{op.type} は権限の組を書くので、ほかの操作とまとめて確定できない")
        event = append_event(
            session, work, actor, op.type, op.model_dump(mode="json"), inverse, undoes_event_id, ctx.held_changes,
            recorded.changes,
        )
        await session.flush()
    except UndoConflictError as e:
        await session.rollback()
        raise await _record_undo_conflict(session, actor, work_id, undoes_event_id, e) from e
    except Exception:
        await session.rollback()
        raise

    if not commit:
        return event
    await authz.write(ctx.tuple_writes, ctx.tuple_deletes)
    try:
        await session.commit()
    except Exception:
        await authz.write(ctx.tuple_deletes, ctx.tuple_writes)
        raise
    return event


def _conflict_message(conflicts: list[dict[str, Any]]) -> str:
    parts = []
    for c in conflicts:
        by = "・".join(f"{e['seq']}番 {e['op_type']}（{e['actor_kind']}:{e['actor_id']}）" for e in c["events"])
        parts.append(f"{c['table']}:{c['id']} の {c['field']} を後で {by or '記録の無い変更'} が変えている")
    return "取り消すと後の変更を上書きするので取り消さない。" + "／".join(parts)


async def _record_undo_conflict(session: AsyncSession, actor: Actor, work_id: str, event_id: str,
                                err: UndoConflictError) -> UndoConflictError:
    """ぶつかった取り消しを記録する（取り消しは当てない）。記録の id を付けて返す。"""
    record = UndoConflict(work_id=work_id, event_id=event_id, actor_kind=actor.kind, actor_id=actor.id,
                          conflicts=err.conflicts)
    session.add(record)
    await session.commit()
    return UndoConflictError(str(err), err.conflicts, record.id)


async def undo(session: AsyncSession, authz: Authz, actor: Actor, work_id: str, event_id: str) -> Event:
    """出来事を取り消す。取り消しも新しい出来事として足す。取り消しの取り消しでやり直しになる。"""
    event = await session.get(Event, event_id)
    if event is None or event.work_id != work_id:
        raise NotFound(f"events:{event_id}")
    if event.inverse is None:
        raise NotUndoable(f"{event.op_type} は取り消せない")
    inverse = event.inverse
    await session.rollback()
    return await submit(session, authz, actor, work_id, inverse, undoes_event_id=event_id)
