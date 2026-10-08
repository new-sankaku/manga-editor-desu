"""上流の変化を見る所（古い印を付けるのはここだけ）。

作品の出来事の列（events.seq）が進んだ作品について、作業ごとに今の上流の版を作り、切り出したときの版と比べる
（upstream_versions.stale_entries）。違えば古い印（HarnessStaleMark）を足し、画面へ出来事 stale を出し、
動いている作業の流れには upstream_changed を知らせる。作り直しは自動ではしない（人が工程の rerun で頼む）。

作り直しを頼んだ作業（rerun_of で後の作業がある物）は、後の作業が見るので見ない。
"""

import asyncio
import logging

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from temporalio.client import Client
from temporalio.service import RPCError, RPCStatusCode

from v3server.canonical_tables.event_and_lock_tables import Event
from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.harness_tables import HarnessStaleMark, HarnessUnit, HarnessWatchCursor
from v3server.database_engine import get_sessionmaker
from v3server.harness.harness_record import add_event
from v3server.harness.upstream_versions import stale_entries, upstream_of

log = logging.getLogger(__name__)
SCAN_SECONDS = 1.0
LIVE = ("done", "cancelled", "failed")


async def scan_once(temporal: Client) -> int:
    """1回見る。足した古い印の数を返す。"""
    signals: list[tuple[str, list[dict]]] = []
    added = 0
    async with get_sessionmaker()() as session:
        work_ids = (await session.execute(select(HarnessUnit.work_id).distinct())).scalars().all()
        for work_id in work_ids:
            top = await session.scalar(select(func.max(Event.seq)).where(Event.work_id == work_id)) or 0
            cursor = await session.get(HarnessWatchCursor, work_id, with_for_update=True)
            if cursor is None:
                cursor = HarnessWatchCursor(work_id=work_id, last_seq=0)
                session.add(cursor)
            if top <= cursor.last_seq:
                continue
            rerun_of = select(HarnessUnit.rerun_of).where(HarnessUnit.rerun_of.is_not(None))
            units = (await session.execute(select(HarnessUnit).where(
                HarnessUnit.work_id == work_id, HarnessUnit.status != "cancelled",
                HarnessUnit.id.not_in(rerun_of)))).scalars().all()
            for u in units:
                current = await upstream_of(session, u.kind, u.work_id, u.target_id)
                new = []
                for e in stale_entries(u.upstream_used, current):
                    got = await session.execute(insert(HarnessStaleMark).values(
                        id=new_id(), work_id=work_id, unit_id=u.id, upstream_key=e["upstream_key"],
                        used_version=e["used_version"], current_version=e["current_version"], effect=e["effect"],
                        reason=e["reason"], status="open").on_conflict_do_nothing().returning(HarnessStaleMark.id))
                    mark_id = got.scalar_one_or_none()
                    if mark_id:
                        new.append({**e, "mark_id": mark_id})
                if new:
                    added += len(new)
                    await add_event(session, work_id, "stale", {"unit_id": u.id, "page_id": u.page_id,
                                                               "target_id": u.target_id, "marks": new},
                                    u.stage_run_id, u.id)
                    if u.status not in LIVE:
                        signals.append((u.workflow_id, new))
            cursor.last_seq = top
        await session.commit()
    for wf_id, entries in signals:
        try:
            await temporal.get_workflow_handle(wf_id).signal("upstream_changed", entries)
        except RPCError as e:
            if e.status != RPCStatusCode.NOT_FOUND:
                raise
    return added


async def run_forever(temporal: Client) -> None:
    while True:
        try:
            await scan_once(temporal)
        except asyncio.CancelledError:
            raise
        except Exception:  # 見る所が落ちても作業者は止めない。次の回でまた見る（記録は残す）
            log.exception("上流の変化を見る所でエラー")
        await asyncio.sleep(SCAN_SECONDS)
