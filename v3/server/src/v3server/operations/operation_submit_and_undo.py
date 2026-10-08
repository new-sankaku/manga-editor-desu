"""操作の窓口。正本を変える唯一の入口（V3ハーネス設計 3章）。

1回の操作の流れ
1. 作品の行を FOR UPDATE で取る（作品ごとに書き込みは1本。V3ハーネス設計 9.3）
2. 権限を確かめる（AIは頼んだ人の権限）
3. ロックを確かめる
4. 正本を変え、出来事を1件追記する
5. 権限の組（OpenFGA）を書き、確定する。確定に失敗したら書いた組を戻す
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.event_and_lock_tables import Event, Lock
from v3server.canonical_tables.work_tree_tables import Work
from v3server.openfga_permissions import Authz
from v3server.operations.all_operation_types import op_adapter
from v3server.operations.operation_base import ApplyContext, OpBase
from v3server.request_actor import Actor
from v3server.v3_error_types import Forbidden, Locked, NotFound, NotUndoable


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


async def submit(
    session: AsyncSession,
    authz: Authz,
    actor: Actor,
    work_id: str,
    op: OpBase | dict[str, Any],
    undoes_event_id: str | None = None,
) -> Event:
    if isinstance(op, dict):
        op = op_adapter.validate_python(op)
    try:
        work = await lock_work(session, work_id)
        if undoes_event_id is not None:
            # 同じ出来事を2人が同時に取り消さないよう、作品の行を取ってから確かめる
            already = (
                await session.execute(select(Event.id).where(Event.undoes_event_id == undoes_event_id))
            ).first()
            if already is not None:
                raise NotUndoable("すでに取り消している")
        scope = await op.scope(session, work)
        if not await authz.check(actor.permission_user, scope.relation, scope.object):
            raise Forbidden(f"{actor.permission_user} に {scope.object} の {scope.relation} が無い")
        for lock in await conflicting_locks(session, actor, scope.lock_targets, scope.page_tree):
            raise locked_error(lock)

        ctx = ApplyContext(session=session, work=work, actor=actor)
        inverse = await op.apply(ctx)
        event = append_event(
            session, work, actor, op.type, op.model_dump(mode="json"), inverse, undoes_event_id
        )
        await session.flush()
    except Exception:
        await session.rollback()
        raise

    await authz.write(ctx.tuple_writes, ctx.tuple_deletes)
    try:
        await session.commit()
    except Exception:
        await authz.write(ctx.tuple_deletes, ctx.tuple_writes)
        raise
    return event


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
