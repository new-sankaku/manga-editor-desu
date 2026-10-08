"""確認待ちの一覧（1つの口で、絞り込みつき）。人の判断を待つ物を1か所に集める。

種類（kind）
- stopped：止まった作業（上限・エラーが続いた・断られた・上流が変わった・閾値未設定などの blocked・一時停止）
- check_failed：検査で外れた候補（落ちた・指摘だけの物）。最後の回の物だけ
- candidates：判断待ちの作業（採用・却下・直す）
- stale：古い印（作り直すか、このままでよいかを人が決める）
- held_ai_change：保留したAIの変更（人の手の印のある所をAIが変えようとした。既存の held_ai_changes）
- stage_review：工程の検査が終わり、次へ進める承認を待つ工程

並びは工程の前のものから（決めごと 5.2）、同じ工程の中は古い順。
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.harness_tables import HarnessCandidate, HarnessStageRun, HarnessStaleMark, HarnessUnit
from v3server.canonical_tables.text_and_layer_tables import HeldAiChange
from v3server.harness.harness_states import STAGE_ORDER, STAGE_TITLES

KINDS = ("stopped", "check_failed", "candidates", "stale", "held_ai_change", "stage_review")


def _item(kind: str, stage: str | None, created_at, **values: Any) -> dict[str, Any]:
    return {"kind": kind, "stage": stage, "stage_title": STAGE_TITLES.get(stage or ""), "created_at": created_at,
            **values}


async def review_items(session: AsyncSession, work_id: str, kinds: list[str] | None = None,
                       stage: str | None = None, page_id: str | None = None,
                       stage_run_id: str | None = None) -> list[dict[str, Any]]:
    want = set(kinds or KINDS)
    unknown = want - set(KINDS)
    if unknown:
        raise ValueError(f"知らない種類: {sorted(unknown)}")
    q = select(HarnessUnit).where(HarnessUnit.work_id == work_id)
    if stage:
        q = q.where(HarnessUnit.stage == stage)
    if page_id:
        q = q.where(HarnessUnit.page_id == page_id)
    if stage_run_id:
        q = q.where(HarnessUnit.stage_run_id == stage_run_id)
    units = (await session.execute(q.order_by(HarnessUnit.created_at))).scalars().all()
    by_id = {u.id: u for u in units}
    out: list[dict[str, Any]] = []
    for u in units:
        base = {"unit_id": u.id, "page_id": u.page_id, "target_id": u.target_id, "unit_kind": u.kind,
                "status": u.status, "step": u.current_step, "attempt": u.attempt}
        if "stopped" in want and u.status in ("stopped", "blocked", "paused"):
            out.append(_item("stopped", u.stage, u.updated_at, reason=u.stop_reason, **base))
        if "candidates" in want and u.status == "awaiting_review":
            out.append(_item("candidates", u.stage, u.updated_at, review=u.review, **base))
    if "check_failed" in want and by_id:
        last = (select(HarnessCandidate.unit_id, func.max(HarnessCandidate.attempt).label("a"))
                .where(HarnessCandidate.unit_id.in_(list(by_id))).group_by(HarnessCandidate.unit_id).subquery())
        rows = (await session.execute(select(HarnessCandidate).join(
            last, (last.c.unit_id == HarnessCandidate.unit_id) & (last.c.a == HarnessCandidate.attempt))
            .where(HarnessCandidate.check_verdict.in_(["drop", "flag"])).order_by(HarnessCandidate.created_at))).scalars()
        for c in rows:
            u = by_id[c.unit_id]
            failed = [f for f in (c.check or {}).get("findings", []) if f.get("ok") is False]
            out.append(_item("check_failed", u.stage, c.created_at, unit_id=u.id, page_id=u.page_id,
                             candidate_id=c.id, image_id=c.image_id, proposal_id=c.proposal_id,
                             verdict=c.check_verdict, failed=failed, dropped_reason=c.dropped_reason))
    if "stale" in want and by_id:
        marks = (await session.execute(select(HarnessStaleMark).where(
            HarnessStaleMark.unit_id.in_(list(by_id)), HarnessStaleMark.status == "open")
            .order_by(HarnessStaleMark.created_at))).scalars().all()
        for m in marks:
            u = by_id[m.unit_id]
            out.append(_item("stale", u.stage, m.created_at, mark_id=m.id, unit_id=u.id, page_id=u.page_id,
                             target_id=u.target_id, effect=m.effect, reason=m.reason, upstream_key=m.upstream_key))
    if "held_ai_change" in want and stage is None and stage_run_id is None:
        hq = select(HeldAiChange).where(HeldAiChange.work_id == work_id, HeldAiChange.status == "open")
        if page_id:
            hq = hq.where(HeldAiChange.page_id == page_id)
        for h in (await session.execute(hq.order_by(HeldAiChange.created_at))).scalars():
            out.append(_item("held_ai_change", None, h.created_at, held_id=h.id, page_id=h.page_id,
                             target_table=h.target_table, target_id=h.target_id, field=h.field,
                             proposed_value=h.proposed_value, current_value=h.current_value))
    if "stage_review" in want and page_id is None:
        sq = select(HarnessStageRun).where(HarnessStageRun.work_id == work_id,
                                           HarnessStageRun.status == "awaiting_review")
        if stage:
            sq = sq.where(HarnessStageRun.stage == stage)
        if stage_run_id:
            sq = sq.where(HarnessStageRun.id == stage_run_id)
        for r in (await session.execute(sq)).scalars():
            out.append(_item("stage_review", r.stage, r.updated_at, stage_run_id=r.id, stage_check=r.stage_check))
    out.sort(key=lambda x: (STAGE_ORDER.get(x["stage"] or "", 99), str(x["created_at"])))
    return out
