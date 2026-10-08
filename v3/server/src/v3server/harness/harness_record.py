"""作業と工程の状態を正本に書き、画面へ送る出来事（HarnessEvent）を足す。状態を書くのはここだけ。

画面（SSE）は出来事の列を id の順に読むので、状態を変えたら必ず出来事も足す（同じトランザクション）。
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.harness_tables import (
    HarnessCandidate,
    HarnessEvent,
    HarnessStageRun,
    HarnessStep,
    HarnessUnit,
)

UNIT_FIELDS = ("status", "current_step", "attempt", "cost_used", "seconds_used", "stop_reason", "review", "result",
               "live", "limits", "upstream_used", "finished_at")
STAGE_FIELDS = ("status", "stage_check", "stop_reason", "next_stage_run_id", "limits")


def now() -> datetime:
    return datetime.now(UTC)


async def unit_counters(session: AsyncSession, unit: HarnessUnit) -> dict[str, Any]:
    """画面のノードに出す数（何回目/上限・費用・候補の数・段の始まり）。"""
    n = await session.scalar(select(func.count()).select_from(HarnessCandidate).where(
        HarnessCandidate.unit_id == unit.id, HarnessCandidate.image_id.is_not(None)))
    step = (await session.execute(select(HarnessStep).where(HarnessStep.unit_id == unit.id)
                                  .order_by(HarnessStep.started_at.desc()).limit(1))).scalar_one_or_none()
    return {
        "unit_id": unit.id, "stage_run_id": unit.stage_run_id, "kind": unit.kind, "target_id": unit.target_id,
        "page_id": unit.page_id, "status": unit.status, "step": unit.current_step, "attempt": unit.attempt,
        "max_attempts": unit.limits.get("max_attempts"), "cost_used": float(unit.cost_used or 0),
        "budget_cost": unit.limits.get("budget_cost"), "seconds_used": float(unit.seconds_used or 0),
        "budget_seconds": unit.limits.get("budget_seconds"), "candidates": n or 0, "stop_reason": unit.stop_reason,
        "step_started_at": step.started_at.isoformat() if step and step.finished_at is None else None,
        "live": unit.live,
    }


async def add_event(session: AsyncSession, work_id: str, kind: str, payload: dict[str, Any],
                    stage_run_id: str | None = None, unit_id: str | None = None) -> None:
    session.add(HarnessEvent(work_id=work_id, stage_run_id=stage_run_id, unit_id=unit_id, kind=kind, payload=payload))


async def patch_unit(session: AsyncSession, unit_id: str, patch: dict[str, Any], event: str = "unit",
                     extra: dict[str, Any] | None = None) -> HarnessUnit:
    """作業の行を変え、今の数を載せた出来事を足す。extra は出来事に添える値（前の段など）。"""
    unit = await session.get(HarnessUnit, unit_id, with_for_update=True)
    unknown = set(patch) - set(UNIT_FIELDS)
    if unknown:
        raise ValueError(f"作業の行に無い項目: {sorted(unknown)}")
    for k, v in patch.items():
        setattr(unit, k, v)
    if patch.get("status") in ("done", "cancelled", "failed") and unit.finished_at is None:
        unit.finished_at = now()
    await session.flush()
    payload = {**await unit_counters(session, unit), **(extra or {})}
    await add_event(session, unit.work_id, event, payload, unit.stage_run_id, unit.id)
    return unit


async def patch_stage(session: AsyncSession, stage_run_id: str, patch: dict[str, Any],
                      extra: dict[str, Any] | None = None) -> HarnessStageRun:
    run = await session.get(HarnessStageRun, stage_run_id, with_for_update=True)
    unknown = set(patch) - set(STAGE_FIELDS)
    if unknown:
        raise ValueError(f"工程の行に無い項目: {sorted(unknown)}")
    for k, v in patch.items():
        setattr(run, k, v)
    await session.flush()
    await add_event(session, run.work_id, "stage",
                    {"stage_run_id": run.id, "episode_id": run.episode_id, "stage": run.stage, "status": run.status,
                     "stop_reason": run.stop_reason, "stage_check": run.stage_check,
                     "next_stage_run_id": run.next_stage_run_id, "limits": run.limits,
                     **(extra or {})}, run.id)
    return run


async def start_step(session: AsyncSession, unit: HarnessUnit, step_id: str, step: str, attempt: int) -> None:
    """段の1回分を始める。同じ id の行があれば使い回す（活動が送り直されても行は1つ。送り直しは始まりを付け直す）。"""
    row = await session.get(HarnessStep, step_id)
    if row is not None and row.finished_at is None:
        return
    if row is None:
        session.add(HarnessStep(id=step_id, unit_id=unit.id, step=step, attempt=attempt, status="running",
                                started_at=now(), cost=0))
    else:
        row.status, row.started_at, row.finished_at = "running", now(), None
    await add_event(session, unit.work_id, "step", {"unit_id": unit.id, "step_id": step_id, "step": step,
                                                   "attempt": attempt, "status": "running",
                                                   "started_at": now().isoformat()}, unit.stage_run_id, unit.id)


async def finish_step(session: AsyncSession, unit: HarnessUnit, step_id: str, status: str,
                      detail: dict[str, Any] | None, cost: float = 0) -> float:
    """段の1回分を終える。動いた秒を返す。"""
    row = await session.get(HarnessStep, step_id)
    if row is None or row.finished_at is not None:
        return 0.0
    row.finished_at = now()
    row.status, row.detail, row.cost = status, detail, cost
    seconds = (row.finished_at - row.started_at).total_seconds()
    await add_event(session, unit.work_id, "step", {"unit_id": unit.id, "step_id": step_id, "step": row.step,
                                                   "attempt": row.attempt, "status": status, "detail": detail,
                                                   "seconds": seconds, "finished_at": row.finished_at.isoformat()},
                    unit.stage_run_id, unit.id)
    return seconds
