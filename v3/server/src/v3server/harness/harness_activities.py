"""ハーネスの活動（Temporal の activity）。作業の流れ・工程の進行役は、正本と外への呼び出しをここ経由でしか触らない。

- run_step：作業の1段を動かす。段の行と出来事を書き、使った費用・秒を作業に足す。動いている間は生存を知らせ続け、
  取り消しはその返事で届く（WAIT_CANCELLATION_COMPLETED で、流れは取り消しが終わるまで待つ）
- record_unit / record_stage：作業・工程の状態を書く（判断待ち・一時停止・止まった理由など）
- prepare_stage：工程の作業を切り出す（同じ工程の実行で2回呼ばれても、作業は増やさない）
- stage_check：工程の検査（S3：ネームの検査と台本の問い。S4：ページごとに絵が揃ったか）
- advance_stage：次の工程の実行を作る
- rerun_units：古い印の付いた作業を作り直す作業を足す（自動では動かさない。人が頼んだときだけ）

失敗の種類（ApplicationError の type）
- blocked：人が決めるまで進めない（閾値未設定・送り先が無い・設定資料が足りない・操作が断られた）
- refused：内容で断られた。送り直さない
- broken_response・generation_failed・job_*：品質や送り先の失敗。流れが「エラーが続いた」に数える
それ以外の例外（通信・データベース）は RetryPolicy で送り直す（resend_limit 回まで）。
"""

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from temporalio import activity
from temporalio.exceptions import ApplicationError

from v3server.canonical_tables.harness_tables import HarnessCandidate, HarnessStageRun, HarnessStaleMark, HarnessUnit
from v3server.canonical_tables.work_tree_tables import Episode, Page, Panel
from v3server.database_engine import get_sessionmaker
from v3server.harness import (
    export_steps,
    name_draft_steps,
    overall_review_steps,
    page_finishing_steps,
    panel_drawing_steps,
    plan_interview_steps,
    settings_sheet_steps,
    structure_steps,
)
from v3server.harness import queue_calls as q
from v3server.harness.harness_record import finish_step, now, patch_stage, patch_unit, start_step
from v3server.harness.harness_states import HUMAN_APPROVE_STAGES, STAGES, UNIT_KIND_OF_STAGE
from v3server.harness.upstream_versions import upstream_of
from v3server.v3_error_types import V3Error

# 段の活動の生存の知らせ（秒）。取り消しはこの返事で届く。2秒から1秒にした（test_harness_perf.py で測った）
HEARTBEAT_SECONDS = 1
STEP_MODULES = {"plan_interview": plan_interview_steps, "structure": structure_steps,
                "settings_sheet": settings_sheet_steps, "name_draft": name_draft_steps,
                "panel_drawing": panel_drawing_steps, "page_finishing": page_finishing_steps,
                "overall_review": overall_review_steps, "export": export_steps}
STEP_FUNCTIONS = ("cut_out", "context", "generate", "check", "fix", "evaluate", "finalize", "discard_round")


@dataclass
class StepInput:
    unit_id: str
    step: str
    attempt: int
    step_id: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class RecordInput:
    target_id: str
    patch: dict[str, Any]
    event: str = "unit"
    extra: dict[str, Any] | None = None


async def _beat() -> None:
    while True:
        activity.heartbeat()
        await asyncio.sleep(HEARTBEAT_SECONDS)


@activity.defn
async def run_step(inp: StepInput) -> dict[str, Any]:
    if inp.step not in STEP_FUNCTIONS:
        raise ApplicationError(f"知らない段: {inp.step}", non_retryable=True)
    async with get_sessionmaker()() as session:
        unit = await session.get(HarnessUnit, inp.unit_id)
        fn = getattr(STEP_MODULES[unit.kind], inp.step)
        if inp.step != "discard_round":
            await start_step(session, unit, inp.step_id, inp.step, inp.attempt)
            # 通信の失敗などで同じ段を送り直しているときは retrying
            status_now = "retrying" if activity.info().attempt > 1 else "running"
            await patch_unit(session, unit.id, {"status": status_now, "current_step": inp.step, "attempt": inp.attempt})
        await session.commit()
    beat = asyncio.create_task(_beat())
    status, detail, out = "failed", None, None
    try:
        out = await fn(unit, {**inp.args, "attempt": inp.attempt})
        status, detail = "done", out
        return out
    except asyncio.CancelledError:
        status, detail = "cancelled", {"reason": "取り消された"}
        raise
    except ApplicationError as e:
        status, detail = "failed", {"type": e.type, "message": e.message, "details": list(e.details)}
        raise
    except V3Error as e:
        # 操作の窓口が断った（権限・ロック・形）。人が直すまで進めない
        status, detail = "failed", {"type": "blocked", "message": str(e)}
        raise q.blocked(f"操作が断られた: {e}") from e
    finally:
        beat.cancel()
        if inp.step != "discard_round":
            await asyncio.shield(_finish(inp, status, detail, (out or {}).get("cost", 0)))


async def _finish(inp: StepInput, status: str, detail: dict[str, Any] | None, cost: float) -> None:
    async with get_sessionmaker()() as session:
        unit = await session.get(HarnessUnit, inp.unit_id)
        seconds = await finish_step(session, unit, inp.step_id, status, detail, cost)
        await patch_unit(session, unit.id, {"cost_used": float(unit.cost_used or 0) + cost,
                                            "seconds_used": float(unit.seconds_used or 0) + seconds})
        await session.commit()


@activity.defn
async def record_unit(inp: RecordInput) -> dict[str, Any]:
    async with get_sessionmaker()() as session:
        unit = await patch_unit(session, inp.target_id, inp.patch, inp.event, inp.extra)
        await session.commit()
        return {"status": unit.status}


@activity.defn
async def unit_usage(unit_id: str) -> dict[str, float]:
    async with get_sessionmaker()() as session:
        unit = await session.get(HarnessUnit, unit_id)
        return {"cost_used": float(unit.cost_used or 0), "seconds_used": float(unit.seconds_used or 0)}


@activity.defn
async def record_stage(inp: RecordInput) -> dict[str, Any]:
    async with get_sessionmaker()() as session:
        run = await patch_stage(session, inp.target_id, inp.patch, inp.extra)
        await session.commit()
        return {"status": run.status}


# ---------------------------------------------------------------- 工程


async def _targets(session, run: HarnessStageRun) -> list[tuple[str, str, str | None]]:
    """（対象の種類, 対象の id, ページの id）の並び。"""
    kind = UNIT_KIND_OF_STAGE.get(run.stage)
    if kind in ("plan_interview", "settings_sheet"):
        # 企画と設定資料は作品に1つ（話ごとの工程の実行から、作品を対象にする）
        return [("work", run.work_id, None)]
    if kind in ("structure", "name_draft", "page_finishing", "overall_review", "export"):
        return [("episode", run.episode_id, None)]
    if kind == "panel_drawing":
        rows = (await session.execute(
            select(Panel).join(Page, Panel.page_id == Page.id)
            .where(Page.episode_id == run.episode_id, Page.removed.is_(False), Panel.removed.is_(False),
                   Panel.human_confirmed.is_(False), Panel.image_id.is_(None))
            .order_by(Page.number, Panel.order))).scalars().all()
        return [("panel", p.id, p.page_id) for p in rows]
    return []


@activity.defn
async def prepare_stage(stage_run_id: str) -> dict[str, Any]:
    """{"kind": 作業の種類（作業を切り出さない工程は None）, "unit_ids": [...]}"""
    async with get_sessionmaker()() as session:
        run = await session.get(HarnessStageRun, stage_run_id, with_for_update=True)
        existing = (await session.execute(select(HarnessUnit).where(
            HarnessUnit.stage_run_id == run.id).order_by(HarnessUnit.created_at))).scalars().all()
        kind = UNIT_KIND_OF_STAGE.get(run.stage)
        if existing:
            # 同じ工程の実行をもう一度始めた（流れが新しく始まった）。終わっていない作業だけ回し直す
            return {"kind": kind, "unit_ids": [u.id for u in existing if u.status not in ("done", "cancelled",
                                                                                           "failed")]}
        ids = []
        completion = list(run.limits["completion"])
        if run.stage in HUMAN_APPROVE_STAGES and "human_approve" not in completion:
            # 人が採るまで終わらない工程（設計 5 の表の「人の確認：必須」）。頼んだ完成条件に無くても足し、出来事に残す
            completion.append("human_approve")
            await patch_stage(session, run.id, {}, {"completion_added": "human_approve",
                                                    "why": f"{run.stage} は人の確認が必須の工程"})
        for target_kind, target_id, page_id in await _targets(session, run):
            unit = HarnessUnit(stage_run_id=run.id, work_id=run.work_id, stage=run.stage, kind=kind,
                               target_kind=target_kind, target_id=target_id, page_id=page_id,
                               completion=completion, limits=run.limits["unit"], spec=run.spec,
                               requested_by=run.requested_by,
                               upstream_used=await upstream_of(session, kind, run.work_id, target_id),
                               status="queued", attempt=0, cost_used=0, seconds_used=0)
            session.add(unit)
            await session.flush()
            unit.workflow_id = f"harness-unit-{unit.id}"
            ids.append(unit.id)
            await patch_unit(session, unit.id, {}, "unit_created")
        await session.commit()
        return {"kind": kind, "unit_ids": ids}


@activity.defn
async def rerun_units(inp: RecordInput) -> list[str]:
    """inp.target_id は工程の実行、inp.patch = {"unit_ids": [...], "by": 人}。古い印を rerun にし、作り直す作業を足す。"""
    ids = []
    async with get_sessionmaker()() as session:
        for uid in inp.patch["unit_ids"]:
            old = await session.get(HarnessUnit, uid)
            if old is None or old.stage_run_id != inp.target_id:
                raise ApplicationError(f"この工程の作業でない: {uid}", type="refused", non_retryable=True)
            again = (await session.execute(select(HarnessUnit).where(HarnessUnit.rerun_of == uid))).scalars().all()
            pending = [u for u in again if u.status not in ("done", "cancelled", "failed")]
            if pending:
                ids.append(pending[0].id)
                continue
            unit = HarnessUnit(stage_run_id=old.stage_run_id, work_id=old.work_id, stage=old.stage, kind=old.kind,
                               target_kind=old.target_kind, target_id=old.target_id, page_id=old.page_id,
                               completion=old.completion, limits=old.limits, spec=old.spec,
                               requested_by=inp.patch["by"],
                               upstream_used=await upstream_of(session, old.kind, old.work_id, old.target_id),
                               status="queued", attempt=0, cost_used=0, seconds_used=0, rerun_of=old.id)
            session.add(unit)
            await session.flush()
            unit.workflow_id = f"harness-unit-{unit.id}"
            marks = (await session.execute(select(HarnessStaleMark).where(
                HarnessStaleMark.unit_id == uid, HarnessStaleMark.status == "open"))).scalars().all()
            for m in marks:
                m.status, m.resolved_at = "rerun", now()
            ids.append(unit.id)
            await patch_unit(session, unit.id, {}, "unit_created", {"rerun_of": uid})
        await session.commit()
    return ids


async def _ask_stage(run: HarnessStageRun, key: str, step: str, question: str) -> tuple[str, str]:
    asker = SimpleNamespace(id=None, work_id=run.work_id, requested_by=run.requested_by)
    return await q.ask_text(asker, f"{run.id}:{key}", step, q.user_message(question, []))


async def _check_name_stage(session, run: HarnessStageRun) -> dict[str, Any]:
    from v3server.canonical_tables.material_and_setting_tables import WorkPlan
    from v3server.canonical_tables.work_tree_tables import Work
    from v3server.harness.upstream_versions import characters_by_name
    from v3server.http_routes.name_check_routes import name_check_thresholds
    from v3server.llm_questions.answer_json_reader import BrokenAnswerError
    from v3server.llm_questions.contradiction_question import (
        CONTRADICTION_VIEWS,
        ScriptLine,
        build_contradiction_question,
        parse_contradiction_answer,
    )
    from v3server.llm_questions.foreshadow_question import (
        build_foreshadow_issues_question,
        parse_foreshadow_issues_answer,
    )
    from v3server.name_checks.name_check_runner import run_name_checks
    from v3server.operations.name_draft_conversion import name_draft_of_episode

    work = await session.get(Work, run.work_id)
    ep = await session.get(Episode, run.episode_id)
    draft = await name_draft_of_episode(session, work, run.episode_id)
    values, used = await name_check_thresholds(session, run.work_id)
    report = run_name_checks(draft, values)
    unset = [r.threshold_key or r.check_id for r in report.results if r.status == "閾値未設定"]
    if unset:
        raise q.blocked("ネームの検査の閾値が未設定: " + "、".join(unset), missing=unset)
    lines = [ScriptLine(f"p{pg.page}-{pn.n}-{i}", ep.number, b.text)
             for pg in draft.pages for pn in pg.panels for i, b in enumerate(pn.balloons or []) if b.text.strip()]
    plan = (await session.execute(select(WorkPlan).where(WorkPlan.work_id == run.work_id))).scalar_one_or_none()
    chars = await characters_by_name(session, run.work_id)
    settings = "\n".join([f"あらすじ：{plan.synopsis}" if plan and plan.synopsis else ""] +
                         [f"{n}：{m.traits or ''}" for n, m in sorted(chars.items())]).strip()
    out: dict[str, Any] = {"name_checks": [r.model_dump() for r in report.results], "thresholds_used": used}
    if not lines:
        out["script"] = "台詞が無いので、台本の問い（矛盾・伏線）は聞いていない"
        return out
    await q.require_route(session, "contradiction")
    await q.require_route(session, "foreshadow")
    try:
        text, _ = await _ask_stage(run, "contradiction", "contradiction",
                                   build_contradiction_question(settings, lines, list(CONTRADICTION_VIEWS)))
        out["contradictions"] = [i.model_dump() for i in parse_contradiction_answer(text, lines)]
        text, _ = await _ask_stage(run, "foreshadow", "foreshadow", build_foreshadow_issues_question(settings, lines))
        out["foreshadow"] = [i.model_dump() for i in parse_foreshadow_issues_answer(text, lines)]
    except BrokenAnswerError as e:
        raise ApplicationError(f"台本の問いの答えの形が崩れた: {e}", type="broken_response", non_retryable=True) from e
    return out


async def _check_drawing_stage(session, run: HarnessStageRun) -> dict[str, Any]:
    flagged = (await session.execute(
        select(HarnessCandidate.unit_id).join(HarnessUnit, HarnessUnit.id == HarnessCandidate.unit_id)
        .where(HarnessUnit.stage_run_id == run.id, HarnessCandidate.check_verdict == "flag",
               HarnessCandidate.picked.is_(True)))).scalars().all()
    drift = await panel_drawing_steps.drift_check(session, run)
    return {"pages": await panel_drawing_steps.page_summary(session, run), "flagged_units": sorted(set(flagged)),
            **drift,
            "note": "コマをまたぐ一致は、設定資料の絵と同じ人物か（CCIP）だけを見る。服・背景の一致は人が見る"}


async def _stage_results(session, run: HarnessStageRun) -> dict[str, Any]:
    """S0〜S2・S5〜S7：作業の検査は作業の中で済んでいる。工程としては、採った候補の指摘を並べる。"""
    rows = (await session.execute(
        select(HarnessUnit, HarnessCandidate).join(HarnessCandidate, HarnessCandidate.unit_id == HarnessUnit.id)
        .where(HarnessUnit.stage_run_id == run.id, HarnessCandidate.picked.is_(True)))).all()
    out = []
    for u, cand in rows:
        if u.status != "done":
            continue
        flags = [f for f in (cand.check or {}).get("findings", []) if f.get("ok") is False]
        out.append({"unit_id": u.id, "candidate_id": cand.id, "flags": [f["name"] for f in flags]})
    return {"picked": out}


@activity.defn
async def stage_check(stage_run_id: str) -> dict[str, Any]:
    beat = asyncio.create_task(_beat())
    try:
        async with get_sessionmaker()() as session:
            run = await session.get(HarnessStageRun, stage_run_id)
            units = (await session.execute(select(HarnessUnit).where(HarnessUnit.stage_run_id == run.id))).scalars().all()
            summary: dict[str, int] = {}
            for u in units:
                summary[u.status] = summary.get(u.status, 0) + 1
            result: dict[str, Any] = {"units": summary}
            try:
                if run.stage == "S3":
                    result.update(await _check_name_stage(session, run))
                elif run.stage == "S4":
                    result.update(await _check_drawing_stage(session, run))
                else:
                    result.update(await _stage_results(session, run))
            except V3Error as e:
                raise q.blocked(f"工程の検査ができない: {e}") from e
            await patch_stage(session, run.id, {"stage_check": result})
            await session.commit()
            return result
    finally:
        beat.cancel()


@activity.defn
async def advance_stage(inp: RecordInput) -> str | None:
    """次の工程の実行を作る（同じ実行から2回呼ばれても1つ）。S7 の次は無い（None）。"""
    async with get_sessionmaker()() as session:
        run = await session.get(HarnessStageRun, inp.target_id, with_for_update=True)
        if run.next_stage_run_id:
            return run.next_stage_run_id
        i = STAGES.index(run.stage)
        if i + 1 >= len(STAGES):
            await patch_stage(session, run.id, {"status": "done"}, {"approved_by": inp.patch["by"]})
            await session.commit()
            return None
        nxt = HarnessStageRun(work_id=run.work_id, episode_id=run.episode_id, stage=STAGES[i + 1], status="queued",
                              requested_by=inp.patch["by"], limits=run.limits, spec=run.spec,
                              workflow_id=run.workflow_id)
        session.add(nxt)
        await session.flush()
        await patch_stage(session, run.id, {"status": "done", "next_stage_run_id": nxt.id},
                          {"approved_by": inp.patch["by"]})
        await patch_stage(session, nxt.id, {})
        await session.commit()
        return nxt.id


ACTIVITIES = [run_step, record_unit, unit_usage, record_stage, prepare_stage, rerun_units, stage_check, advance_stage]
TIMEOUT = timedelta(seconds=30)
