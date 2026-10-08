"""文章の案を作る工程（S0・S1・S2）と、プログラムが作る工程（S5〜S7）の作業の段が共に使う部品。

候補の中身は HarnessCandidate.content に置く（案の JSON・検査の材料）。正本へ書くのは人が採った後（finalize）だけ。

- 検査の指摘は {"name", "ok", "drops", "detail"}。drops=True の指摘が ok=False なら候補を落とす（形・数のように
  プログラムで決まる物）。drops=False は指摘だけ（LLM の判定・仮の閾値。精度を測っていない物で候補を落とさない）
- 評価役を置かない工程は、指摘の少ない候補を初めの候補にする（選ぶのは人）
"""

from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from temporalio.exceptions import ApplicationError

from v3server.canonical_tables.harness_tables import HarnessCandidate, HarnessUnit
from v3server.canonical_tables.threshold_and_finding_tables import Threshold
from v3server.canonical_tables.work_tree_tables import Episode, Work
from v3server.database_engine import get_sessionmaker
from v3server.harness import queue_calls as q
from v3server.llm_questions.answer_json_reader import BrokenAnswerError
from v3server.request_actor import Actor


def ai(unit: HarnessUnit) -> Actor:
    return Actor(kind="ai", id="harness", on_behalf_of=unit.requested_by)


def human(by: str) -> Actor:
    """人が採った案を正本へ書くときの操作の出し手（採った人）。"""
    return Actor(kind="human", id=by)


def spec_of(unit: HarnessUnit, key: str, model):
    """作業の決めごと。無ければ blocked（工程の決めごとを PUT .../stages/{id}/spec で足してから再開する）。"""
    if key not in (unit.spec or {}):
        raise q.blocked(f"作業の決めごと spec.{key} が無い。工程の決めごとに足してから再開する", spec=key)
    return model.model_validate(unit.spec[key])


async def cut_out_episode(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    async with get_sessionmaker()() as session:
        if unit.target_kind == "work":
            if await session.get(Work, unit.target_id) is None:
                raise ApplicationError("作品が無い", type="refused", non_retryable=True)
            return {"work_id": unit.target_id}
        ep = await session.get(Episode, unit.target_id)
        if ep is None or ep.removed:
            raise ApplicationError("話が無い（消された）", type="refused", non_retryable=True)
        return {"episode_id": ep.id}


async def _candidate(session, unit: HarnessUnit, attempt: int, i: int) -> HarnessCandidate:
    hkey = f"{unit.id}:a{attempt}:gen{i}"
    cand = (await session.execute(select(HarnessCandidate).where(
        HarnessCandidate.harness_key == hkey))).scalar_one_or_none()
    if cand is None:
        cand = HarnessCandidate(unit_id=unit.id, attempt=attempt, k_index=i, harness_key=hkey, status="requested",
                                picked=False, fix_round=0)
        session.add(cand)
        await session.commit()
    return cand


async def ask_candidates(unit: HarnessUnit, args: dict[str, Any], step: str, question: str,
                         read: Callable[[str], dict[str, Any]], images: list[str] | None = None) -> dict[str, Any]:
    """k 個の案を LLM に頼み、read（答えの文 → 中身の辞書。崩れたら BrokenAnswerError）で読んで候補の中身にする。
    崩れた答えはその候補だけ落とす。"""
    attempt, k = args["attempt"], int(unit.limits["candidates_per_attempt"])
    job_ids, out = [], []
    for i in range(k):
        async with get_sessionmaker()() as session:
            cand = await _candidate(session, unit, attempt, i)
            cid, done = cand.id, cand.content is not None
        if done:
            out.append({"candidate_id": cid, "status": "generated"})
            continue
        text, jid = await q.ask_text(unit, f"{unit.id}:a{attempt}:gen{i}", step, q.user_message(question, images or []))
        job_ids.append(jid)
        async with get_sessionmaker()() as session:
            cand = await session.get(HarnessCandidate, cid)
            cand.job_id = jid
            try:
                cand.content, cand.status = read(text), "generated"
            except BrokenAnswerError as e:
                cand.status, cand.dropped_reason = "failed", f"答えの形が崩れた: {e}"
            await session.commit()
            out.append({"candidate_id": cid, "status": cand.status})
    async with get_sessionmaker()() as session:
        cost = await q.jobs_cost(session, job_ids)
    if not any(o["status"] == "generated" for o in out):
        raise ApplicationError("案が1つも読めなかった（答えの形が崩れた）", type="broken_response", non_retryable=True)
    return {"candidates": out, "cost": cost, "job_ids": job_ids}


async def one_candidate(unit: HarnessUnit, args: dict[str, Any], make: Callable[[], Awaitable[dict[str, Any]]],
                        why: str) -> dict[str, Any]:
    """作業役の案が1つしか無い工程（人が置いた物を検査する・プログラムが書き出す）。candidates_per_attempt は使わない
    （同じ物を何個作っても同じになるため）。why をその理由として段の結果に書く。"""
    async with get_sessionmaker()() as session:
        cand = await _candidate(session, unit, args["attempt"], 0)
        cid, content = cand.id, cand.content
    if content is None:
        content = await make()
        async with get_sessionmaker()() as session:
            cand = await session.get(HarnessCandidate, cid)
            cand.content, cand.status = content, "generated"
            await session.commit()
    return {"candidates": [{"candidate_id": cid, "status": "generated"}], "cost": content.get("cost", 0),
            "job_ids": content.get("job_ids", []), "single": why}


async def thresholds_of(session, work_id: str, prefix: str, needed: dict[str, str]) -> dict[str, dict[str, Any]]:
    """閾値 {名前: {value, status, source}}。needed（名前 → 何の閾値か）のどれかが無ければ blocked（黙って決めない）。"""
    rows = (await session.execute(select(Threshold).where(
        Threshold.work_id == work_id, Threshold.key.like(prefix + "%")))).scalars().all()
    got = {t.key[len(prefix):]: t for t in rows if t.status != "rejected"}
    missing = [k for k in needed if k not in got]
    if missing:
        raise q.blocked("閾値が未設定: " + "、".join(f"{prefix}{k}（{needed[k]}）" for k in missing),
                        missing=[prefix + k for k in missing])
    return {k: {"value": float(t.value["value"]), "status": t.status, "source": t.source} for k, t in got.items()}


def finding(name: str, ok: bool | None, drops: bool, detail: str, **extra: Any) -> dict[str, Any]:
    return {"name": name, "ok": ok, "drops": drops, "detail": detail, **extra}


async def check_candidates(unit: HarnessUnit, args: dict[str, Any],
                           judge: Callable[[Any], Awaitable[list[dict[str, Any]]]]) -> dict[str, Any]:
    attempt = args["attempt"]
    out, failed = [], set()
    async with get_sessionmaker()() as session:
        cands = (await session.execute(select(HarnessCandidate).where(
            HarnessCandidate.unit_id == unit.id, HarnessCandidate.attempt == attempt,
            HarnessCandidate.status == "generated").order_by(HarnessCandidate.k_index))).scalars().all()
        ids = [c.id for c in cands]
    for cid in ids:
        # 判定は LLM・検出器を待つことがあるので、データベースのつなぎを持ったまま待たない
        async with get_sessionmaker()() as session:
            c = await session.get(HarnessCandidate, cid)
            snap = SimpleNamespace(id=c.id, content=c.content, image_id=c.image_id, attempt=c.attempt)
        findings = await judge(snap)
        async with get_sessionmaker()() as session:
            c = await session.get(HarnessCandidate, cid)
            dropped = [f for f in findings if f["ok"] is False and f["drops"]]
            c.check = {"findings": findings}
            c.check_verdict = "drop" if dropped else ("flag" if any(f["ok"] is False for f in findings) else "pass")
            if dropped:
                c.dropped_reason = "検査で落ちた: " + "、".join(f["name"] for f in dropped)
            failed |= {f["name"] for f in findings if f["ok"] is False}
            out.append({"candidate_id": c.id, "verdict": c.check_verdict})
            await session.commit()
    return {"results": out, "passed": sum(1 for o in out if o["verdict"] != "drop"), "cost": 0, "job_ids": [],
            "failure": "check:" + ",".join(sorted(failed))}


async def pick_fewest_flags(unit: HarnessUnit, args: dict[str, Any], why: str) -> dict[str, Any]:
    async with get_sessionmaker()() as session:
        cands = (await session.execute(select(HarnessCandidate).where(
            HarnessCandidate.unit_id == unit.id, HarnessCandidate.attempt == args["attempt"],
            HarnessCandidate.check_verdict.in_(["pass", "flag"])).order_by(HarnessCandidate.k_index))).scalars().all()
        if not cands:
            return {"picked": None, "why": "選べる案が無い", "cost": 0, "job_ids": [], "disagree": False,
                    "failure": "evaluate:なし"}

        def flags(c):
            return sum(1 for f in c.check["findings"] if f["ok"] is False)

        best = min(cands, key=flags)
        for c in cands:
            c.picked = c.id == best.id
            c.evaluation = {"flags": flags(c), "by": "program"}
        await session.commit()
        return {"picked": best.id, "why": [why], "cost": 0, "job_ids": [], "disagree": False, "failure": None}


async def discard_candidates(unit: HarnessUnit, args: dict[str, Any],
                             also: Callable[[Any, HarnessCandidate], Awaitable[None]] | None = None) -> dict[str, Any]:
    async with get_sessionmaker()() as session:
        cands = (await session.execute(select(HarnessCandidate).where(
            HarnessCandidate.unit_id == unit.id, HarnessCandidate.attempt == args["attempt"]))).scalars().all()
        for c in cands:
            if c.status == "requested":
                c.status = "cancelled"
            c.dropped_reason = c.dropped_reason or args["reason"]
            if also is not None:
                await also(session, c)
        await session.commit()
    return {"discarded": [c.id for c in cands]}


async def picked_content(session, args: dict[str, Any]) -> HarnessCandidate:
    cand = await session.get(HarnessCandidate, args["candidate_id"])
    if cand is None or cand.content is None:
        raise ApplicationError("採る候補に中身が無い", type="refused", non_retryable=True)
    return cand
