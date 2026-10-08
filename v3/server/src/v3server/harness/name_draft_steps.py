"""ネーム（S3）の1話の作業の段。作業の流れ（unit_workflow.py）が段ごとに活動として呼ぶ。

- 文脈：企画のあらすじと、採った設定資料の人物（名前と特徴）から、ネームを作る問い（name_draft_question）を組む
- 生成：k 個の案を LLM に頼み、答えを読んでネームの案（SubmitNameProposal、made_by=ai）として出す。形の崩れた答えは
  その候補だけ落とす
- 検査：今のネームの検査（name_check_runner）を案に当てる。確定の閾値で不合格なら落とし、仮の閾値なら指摘だけ。
  閾値が無い検査があれば blocked（閾値未設定）で止める
- 評価：ネームの良し悪しを選ぶ評価役は置かない（数で見られるのは形だけ。V3検証の結果 2-16）。指摘の少ない案を
  初めの候補として並べ、選ぶのは人
- 確定：人の採用で ApplyNameProposal を人の操作として通す
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from temporalio.exceptions import ApplicationError

from v3server.canonical_tables.harness_tables import HarnessCandidate, HarnessUnit
from v3server.canonical_tables.material_and_setting_tables import WorkPlan
from v3server.canonical_tables.name_proposal_tables import NameProposal
from v3server.canonical_tables.work_tree_tables import Episode, Work
from v3server.database_engine import get_sessionmaker
from v3server.harness import queue_calls as q
from v3server.harness.upstream_versions import characters_by_name
from v3server.http_routes.name_check_routes import name_check_thresholds
from v3server.llm_questions.answer_json_reader import BrokenAnswerError
from v3server.llm_questions.name_draft_question import build_name_draft_question, parse_name_draft_answer
from v3server.name_checks.name_check_runner import run_name_checks
from v3server.name_structure.reading_direction import PageSpec
from v3server.operations.name_draft_conversion import READING_DIRECTION, name_draft_of_proposal
from v3server.operations.name_proposal_operations import (
    ApplyNameProposal,
    SetNameProposalStatus,
    SubmitNameProposal,
)
from v3server.operations.operation_submit_and_undo import submit
from v3server.request_actor import Actor


class NameSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_count: int = Field(ge=1, le=200)


def _ai(unit: HarnessUnit) -> Actor:
    return Actor(kind="ai", id="harness", on_behalf_of=unit.requested_by)


async def _work(session, unit: HarnessUnit) -> Work:
    work = await session.get(Work, unit.work_id)
    if work.page_spec is None or work.first_page_is_left is None:
        raise q.blocked("作品の寸法（page_spec）と1ページ目の位置（first_page_is_left）がまだ決まっていない")
    return work


async def cut_out(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    NameSpec.model_validate(unit.spec.get("name"))
    async with get_sessionmaker()() as session:
        ep = await session.get(Episode, unit.target_id)
        if ep is None or ep.removed:
            raise ApplicationError("話が無い（消された）", type="refused", non_retryable=True)
        await _work(session, unit)
        return {"episode_id": ep.id}


async def context(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    spec = NameSpec.model_validate(unit.spec["name"])
    async with get_sessionmaker()() as session:
        work = await _work(session, unit)
        await q.require_route(session, "name_draft")
        plan = (await session.execute(select(WorkPlan).where(WorkPlan.work_id == unit.work_id))).scalar_one_or_none()
        if plan is None or not (plan.synopsis or "").strip():
            raise q.blocked("企画のあらすじが無い（S0 で人が書く）")
        chars = await characters_by_name(session, unit.work_id)
        if not chars:
            raise q.blocked("設定資料に採った人物が無い（S2 で人が採る）")
        characters = [(n, m.traits or "") for n, m in sorted(chars.items())]
        _, used = await name_check_thresholds(session, unit.work_id)
        plot = plan.synopsis
        if args.get("reject_reason"):
            # 却下の理由は、あらすじの後ろに人の言葉のまま添える（問いの形は変えない）
            plot += f"\n\n前の案を見た人の指摘：{args['reject_reason']}"
        question = build_name_draft_question(plot, characters, spec.page_count,
                                             READING_DIRECTION[work.reading_direction], work.first_page_is_left)
    return {"question": question, "thresholds": used, "cost": 0, "job_ids": []}


async def generate(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    ctx, attempt, k = args["context"], args["attempt"], unit.limits["candidates_per_attempt"]
    job_ids, out = [], []
    for i in range(k):
        hkey = f"{unit.id}:a{attempt}:gen{i}"
        async with get_sessionmaker()() as session:
            cand = (await session.execute(select(HarnessCandidate).where(
                HarnessCandidate.harness_key == hkey))).scalar_one_or_none()
            if cand is None:
                cand = HarnessCandidate(unit_id=unit.id, attempt=attempt, k_index=i, harness_key=hkey,
                                        status="requested", picked=False)
                session.add(cand)
                await session.commit()
            cid, done_proposal = cand.id, cand.proposal_id
        if done_proposal:
            out.append({"candidate_id": cid, "proposal_id": done_proposal, "status": "generated"})
            continue
        text, jid = await q.ask_text(unit, hkey, "name_draft", q.user_message(ctx["question"], []))
        job_ids.append(jid)
        async with get_sessionmaker()() as session:
            work = await session.get(Work, unit.work_id)
            cand = await session.get(HarnessCandidate, cid)
            cand.job_id = jid
            try:
                draft = parse_name_draft_answer(text, READING_DIRECTION[work.reading_direction],
                                                PageSpec.model_validate(work.page_spec), work.first_page_is_left)
            except BrokenAnswerError as e:
                cand.status, cand.dropped_reason = "failed", f"答えの形が崩れた: {e}"
                await session.commit()
                out.append({"candidate_id": cid, "proposal_id": None, "status": "failed"})
                continue
            op = SubmitNameProposal(episode_id=unit.target_id, made_by="ai",
                                    pages=draft.pages, job_id=jid, note=f"ハーネス {unit.id} の{attempt}回目")
            await submit(session, await q.authz(), _ai(unit), unit.work_id, op)
            cand = await session.get(HarnessCandidate, cid)
            cand.proposal_id, cand.status = op.id, "generated"
            await session.commit()
            out.append({"candidate_id": cid, "proposal_id": op.id, "status": "generated"})
    async with get_sessionmaker()() as session:
        cost = await q.jobs_cost(session, job_ids)
    if not any(o["proposal_id"] for o in out):
        raise ApplicationError("案が1つも読めなかった（答えの形が崩れた）", type="broken_response", non_retryable=True)
    return {"candidates": out, "cost": cost, "job_ids": job_ids}


async def check(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    attempt = args["attempt"]
    out, failed_names = [], set()
    async with get_sessionmaker()() as session:
        work = await session.get(Work, unit.work_id)
        values, used = await name_check_thresholds(session, unit.work_id)
        cands = (await session.execute(select(HarnessCandidate).where(
            HarnessCandidate.unit_id == unit.id, HarnessCandidate.attempt == attempt,
            HarnessCandidate.proposal_id.is_not(None)).order_by(HarnessCandidate.k_index))).scalars().all()
        for c in cands:
            prop = await session.get(NameProposal, c.proposal_id)
            report = run_name_checks(name_draft_of_proposal(work, prop.pages), values)
            unset = [r.threshold_key or r.check_id for r in report.results if r.status == "閾値未設定"]
            if unset:
                raise q.blocked("ネームの検査の閾値が未設定: " + "、".join(unset), missing=unset)
            findings = []
            for r in report.results:
                status = used.get(r.threshold_key, {}).get("status") if r.threshold_key else None
                ok = None if r.status == "データなし" else r.status == "合格"
                findings.append({"name": r.title, "ok": ok, "threshold_status": status,
                                 "detail": "；".join(r.report_lines()[:3])})
            dropped = [f for f in findings if f["ok"] is False and f["threshold_status"] in (None, "verified")]
            c.check = {"findings": findings}
            c.check_verdict = "drop" if dropped else ("flag" if any(f["ok"] is False for f in findings) else "pass")
            if dropped:
                c.dropped_reason = "検査で落ちた: " + "、".join(f["name"] for f in dropped)
            failed_names |= {f["name"] for f in findings if f["ok"] is False}
            out.append({"candidate_id": c.id, "verdict": c.check_verdict})
        await session.commit()
    passed = [o for o in out if o["verdict"] != "drop"]
    return {"results": out, "passed": len(passed), "cost": 0, "job_ids": [],
            "failure": "check:" + ",".join(sorted(failed_names))}


async def evaluate(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    """評価役は置かない。指摘の少ない案を初めの候補にする（選ぶのは人）。"""
    async with get_sessionmaker()() as session:
        cands = (await session.execute(select(HarnessCandidate).where(
            HarnessCandidate.unit_id == unit.id, HarnessCandidate.attempt == args["attempt"],
            HarnessCandidate.check_verdict.in_(["pass", "flag"])).order_by(HarnessCandidate.k_index))).scalars().all()
        if not cands:
            return {"picked": None, "why": "選べる案が無い", "picks": [], "cost": 0, "job_ids": [], "disagree": False,
                    "failure": "evaluate:なし"}

        def flags(c):
            return sum(1 for f in c.check["findings"] if f["ok"] is False)

        best = min(cands, key=flags)
        for c in cands:
            c.picked = c.id == best.id
            c.evaluation = {"flags": flags(c), "by": "program"}
        await session.commit()
        return {"picked": best.id, "why": ["指摘の少ない案（評価役は置かない）"], "picks": [best.id], "cost": 0,
                "job_ids": [], "disagree": False, "failure": None}


async def finalize(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    async with get_sessionmaker()() as session:
        cand = await session.get(HarnessCandidate, args["candidate_id"])
        prop = await session.get(NameProposal, cand.proposal_id)
        if prop.status != "open":
            return {"proposal_id": prop.id, "already": prop.status}
        await submit(session, await q.authz(), Actor(kind="human", id=args["by"]), unit.work_id,
                     ApplyNameProposal(id=prop.id))
        return {"proposal_id": prop.id}


async def discard_round(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    done = []
    async with get_sessionmaker()() as session:
        cands = (await session.execute(select(HarnessCandidate).where(
            HarnessCandidate.unit_id == unit.id, HarnessCandidate.attempt == args["attempt"]))).scalars().all()
        for c in cands:
            if c.status == "requested":
                c.status = "cancelled"
            c.dropped_reason = c.dropped_reason or args["reason"]
            if c.proposal_id:
                prop = await session.get(NameProposal, c.proposal_id)
                if prop.status == "open":
                    await submit(session, await q.authz(), Actor(kind="human", id=args["by"]), unit.work_id,
                                 SetNameProposalStatus(id=prop.id, status="discarded"))
                    done.append(prop.id)
        await session.commit()
    return {"discarded": done}
