"""ロックの取得・解放・取り返し（V3ハーネス設計 4.3）。

- ページ・コマ・個別の3段。ページのロックは、その中のコマ・個別のロックとぶつかる
- 人は、AIが持っているロックをいつでも取り返せる。取り返したAIの作業は、呼んだ側が取り消す（返り値の job_id）
- 人どうし・AIどうしでは取り返さない
- 取得・解放・取り返しはどれも出来事として残す（取り消しはできない）
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .actor import Actor
from .authz import Authz
from .config import get_settings
from .errors import Forbidden, NotFound
from .models import Lock, Page, Panel
from .ops.catalog import get_in_work, page_obj
from .ops.gateway import append_event, conflicting_locks, lock_work, locked_error


@dataclass
class AcquireResult:
    lock: Lock
    # 取り返したAIのロックが持っていた作業。呼んだ側で取り消す
    preempted_job_ids: list[str] = field(default_factory=list)


async def _page_of(session: AsyncSession, work_id: str, kind: str, target_id: str, page_id: str | None) -> str:
    if kind == "page":
        await get_in_work(session, Page, target_id, work_id)
        return target_id
    if kind == "panel":
        return (await get_in_work(session, Panel, target_id, work_id)).page_id
    # 個別（吹き出し・人物など）はコマの中の物。どのページかは呼ぶ側が渡す
    if page_id is None:
        raise NotFound("個別のロックにはページが要る")
    await get_in_work(session, Page, page_id, work_id)
    return page_id


async def acquire(
    session: AsyncSession,
    authz: Authz,
    actor: Actor,
    work_id: str,
    target_kind: Literal["page", "panel", "item"],
    target_id: str,
    reason: str,
    page_id: str | None = None,
    job_id: str | None = None,
) -> AcquireResult:
    try:
        work = await lock_work(session, work_id)
        page_id = await _page_of(session, work_id, target_kind, target_id, page_id)
        if not await authz.check(actor.permission_user, "can_draw", page_obj(page_id)):
            raise Forbidden(f"{actor.permission_user} に {page_obj(page_id)} の can_draw が無い")

        if target_kind == "page":
            conflicts = await conflicting_locks(session, actor, [("page", page_id)], page_tree=page_id)
        else:
            conflicts = await conflicting_locks(session, actor, [(target_kind, target_id), ("page", page_id)])

        preempted: list[str] = []
        for c in conflicts:
            if actor.kind == "human" and c.holder_kind == "ai":
                if c.job_id:
                    preempted.append(c.job_id)
                append_event(
                    session,
                    work,
                    actor,
                    "lock_preempted",
                    {"lock_id": c.id, "target_kind": c.target_kind, "target_id": c.target_id,
                     "holder_id": c.holder_id, "job_id": c.job_id},
                )
                await session.delete(c)
            else:
                raise locked_error(c)
        await session.flush()

        expires_at = datetime.now(UTC) + timedelta(seconds=get_settings().lock_ttl_seconds)
        lock = await _existing(session, target_kind, target_id)
        if lock is not None:
            # 期限切れか自分のロック。持ち主を付け替えて延ばす
            lock.holder_kind, lock.holder_id = actor.kind, actor.id
            lock.reason, lock.job_id, lock.expires_at, lock.page_id = reason, job_id, expires_at, page_id
        else:
            lock = Lock(
                work_id=work_id,
                target_kind=target_kind,
                target_id=target_id,
                page_id=page_id,
                holder_kind=actor.kind,
                holder_id=actor.id,
                reason=reason,
                job_id=job_id,
                expires_at=expires_at,
            )
            session.add(lock)
        await session.flush()
        append_event(
            session,
            work,
            actor,
            "lock_acquired",
            {"lock_id": lock.id, "target_kind": target_kind, "target_id": target_id, "reason": reason,
             "expires_at": expires_at.isoformat()},
        )
        await session.commit()
        return AcquireResult(lock, preempted)
    except Exception:
        await session.rollback()
        raise


async def release(session: AsyncSession, actor: Actor, work_id: str, lock_id: str) -> None:
    try:
        work = await lock_work(session, work_id)
        lock = await session.get(Lock, lock_id)
        if lock is None or lock.work_id != work_id:
            raise NotFound(f"locks:{lock_id}")
        if not actor.holds(lock.holder_kind, lock.holder_id):
            raise Forbidden("自分のロックだけ外せる。AIのロックを取り返すときは取得する")
        append_event(
            session, work, actor, "lock_released",
            {"lock_id": lock.id, "target_kind": lock.target_kind, "target_id": lock.target_id},
        )
        await session.delete(lock)
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def _existing(session: AsyncSession, kind: str, target_id: str) -> Lock | None:
    return (
        await session.execute(select(Lock).where(Lock.target_kind == kind, Lock.target_id == target_id))
    ).scalar_one_or_none()
