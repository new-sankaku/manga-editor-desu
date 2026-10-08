"""画面への生の状態（SSE）と、つなぎ直しのときの今の状態（snapshot）。

- 状態の変化は正本（harness_events）に書いた順に流す。id が SSE の id で、つなぎ直しは Last-Event-ID（か ?after=）
  から続きを流す。画面は snapshot を取ってから、その last_event_id の続きを受ける（取りこぼしも重なりも無い。
  同じ出来事を2回当てても結果が変わらない形で送る：どの出来事も「今の値」を全部載せる）
- ComfyUI の段数と途中の絵（service_call_progress）は、変わった物だけ event: progress で流す（id は付けない。
  消えても次の値で上書きされる物なので、つなぎ直しでは snapshot の値を使う）
"""

import asyncio
import json
from collections.abc import AsyncIterator, Callable, Awaitable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.harness_tables import (
    HarnessCandidate,
    HarnessEvent,
    HarnessStageRun,
    HarnessStaleMark,
    HarnessStep,
    HarnessUnit,
    ServiceCallProgress,
)
from v3server.database_engine import get_sessionmaker
from v3server.harness.harness_record import unit_counters

POLL_SECONDS = 0.2
KEEPALIVE_SECONDS = 15
PROGRESS_OVERLAP = timedelta(seconds=2)
BATCH = 500

STAGE_FIELDS = ("id", "episode_id", "stage", "status", "requested_by", "limits", "stage_check", "stop_reason",
                "next_stage_run_id", "created_at", "updated_at")
STEP_FIELDS = ("id", "unit_id", "step", "attempt", "status", "started_at", "finished_at", "detail", "cost")
CANDIDATE_FIELDS = ("id", "unit_id", "attempt", "k_index", "job_id", "image_id", "proposal_id", "seed", "status",
                    "check", "check_verdict", "evaluation", "picked", "dropped_reason", "created_at")
MARK_FIELDS = ("id", "unit_id", "upstream_key", "effect", "reason", "status", "created_at")


def row_of(obj, fields) -> dict[str, Any]:
    out = {}
    for f in fields:
        v = getattr(obj, f)
        out[f] = v.isoformat() if isinstance(v, datetime) else float(v) if f == "cost" and v is not None else v
    return out


def _progress(p: ServiceCallProgress, cand: HarnessCandidate) -> dict[str, Any]:
    return {"candidate_id": cand.id, "unit_id": cand.unit_id, "attempt": cand.attempt, "k_index": cand.k_index,
            "state": p.state, "value": p.value, "max": p.max, "updated_at": p.updated_at.isoformat(),
            "preview": (f"data:{p.preview_media_type};base64,{p.preview_b64}" if p.preview_b64 else None)}


async def _progress_rows(session: AsyncSession, work_id: str, since: datetime | None):
    q = (select(ServiceCallProgress, HarnessCandidate)
         .join(HarnessCandidate, HarnessCandidate.id == ServiceCallProgress.progress_key)
         .join(HarnessUnit, HarnessUnit.id == HarnessCandidate.unit_id)
         .where(HarnessUnit.work_id == work_id))
    if since is not None:
        q = q.where(ServiceCallProgress.updated_at > since)
    else:
        q = q.where(HarnessCandidate.status == "requested")
    return (await session.execute(q)).all()


async def snapshot(session: AsyncSession, work_id: str, unit_id: str | None = None) -> dict[str, Any]:
    """今の状態の全部。last_event_id は状態を読む前に取る（その後の出来事は SSE で必ず届く）。"""
    last = await session.scalar(select(func.max(HarnessEvent.id)).where(HarnessEvent.work_id == work_id)) or 0
    runs = (await session.execute(select(HarnessStageRun).where(HarnessStageRun.work_id == work_id)
                                  .order_by(HarnessStageRun.created_at))).scalars().all()
    units = (await session.execute(select(HarnessUnit).where(HarnessUnit.work_id == work_id)
                                   .order_by(HarnessUnit.created_at))).scalars().all()
    marks = (await session.execute(select(HarnessStaleMark).where(
        HarnessStaleMark.work_id == work_id, HarnessStaleMark.status == "open"))).scalars().all()
    out: dict[str, Any] = {
        "last_event_id": last,
        "stage_runs": [row_of(r, STAGE_FIELDS) for r in runs],
        "units": [await unit_counters(session, u) for u in units],
        "stale": [row_of(m, MARK_FIELDS) for m in marks],
        "progress": [_progress(p, c) for p, c in await _progress_rows(session, work_id, None)],
    }
    if unit_id is not None:
        out["unit"] = await unit_detail(session, unit_id)
    return out


async def unit_detail(session: AsyncSession, unit_id: str) -> dict[str, Any]:
    u = await session.get(HarnessUnit, unit_id)
    steps = (await session.execute(select(HarnessStep).where(HarnessStep.unit_id == unit_id)
                                   .order_by(HarnessStep.started_at))).scalars().all()
    cands = (await session.execute(select(HarnessCandidate).where(HarnessCandidate.unit_id == unit_id)
                                   .order_by(HarnessCandidate.attempt, HarnessCandidate.k_index))).scalars().all()
    marks = (await session.execute(select(HarnessStaleMark).where(HarnessStaleMark.unit_id == unit_id)
                                   .order_by(HarnessStaleMark.created_at))).scalars().all()
    # 人の判断（採用・却下・直した絵）は段の行に無い。画面の時間の列と戻りの辺の数に使う
    decisions = (await session.execute(select(HarnessEvent).where(
        HarnessEvent.unit_id == unit_id, HarnessEvent.kind == "review").order_by(HarnessEvent.id))).scalars().all()
    return {**await unit_counters(session, u), "review": u.review, "result": u.result, "limits": u.limits,
            "decisions": [{"event_id": e.id, "at": e.created_at.isoformat(), "action": e.payload.get("action"),
                           "by": e.payload.get("by"), "reason": e.payload.get("reason"),
                           "attempt": (e.payload.get("review") or {}).get("attempt")} for e in decisions],
            "completion": u.completion, "rerun_of": u.rerun_of, "upstream_used": u.upstream_used,
            "steps": [row_of(s, STEP_FIELDS) for s in steps], "candidates": [row_of(c, CANDIDATE_FIELDS) for c in cands],
            "stale": [row_of(m, MARK_FIELDS) for m in marks]}


def _sse(data: dict[str, Any], event: str, eid: int | None = None) -> str:
    head = f"id: {eid}\n" if eid is not None else ""
    return f"{head}event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


async def stream(work_id: str, after: int, disconnected: Callable[[], Awaitable[bool]]) -> AsyncIterator[str]:
    yield "retry: 1500\n\n"
    since: datetime | None = None
    seen: dict[str, datetime] = {}
    loop = asyncio.get_running_loop()
    quiet_since = loop.time()
    while not await disconnected():
        sent = False
        async with get_sessionmaker()() as session:
            rows = (await session.execute(select(HarnessEvent).where(
                HarnessEvent.work_id == work_id, HarnessEvent.id > after).order_by(HarnessEvent.id).limit(BATCH))
            ).scalars().all()
            for e in rows:
                after = e.id
                sent = True
                yield _sse({**e.payload, "kind": e.kind, "unit_id": e.unit_id, "stage_run_id": e.stage_run_id,
                            "at": e.created_at.isoformat()}, e.kind, e.id)
            # 次に読む境は、読む前のデータベースの時刻から少し戻した所（書き込みの確定が読むより遅れた物も拾う）。
            # 同じ値を2回送らないよう、鍵ごとに送った時刻を覚える
            t0 = await session.scalar(select(func.clock_timestamp()))
            for p, c in await _progress_rows(session, work_id, since):
                if seen.get(c.id) == p.updated_at:
                    continue
                seen[c.id] = p.updated_at
                sent = True
                yield _sse(_progress(p, c), "progress")
            since = t0 - PROGRESS_OVERLAP
        if sent:
            quiet_since = loop.time()
        elif loop.time() - quiet_since > KEEPALIVE_SECONDS:
            quiet_since = loop.time()
            yield ": keepalive\n\n"
        await asyncio.sleep(POLL_SECONDS)
