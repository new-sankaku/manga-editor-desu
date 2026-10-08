"""構成（S1）の作業の段。対象は話。1話のページ配分（ページごとの中身と役目）・見せ場・伏線を作る。

- 文脈：企画のあらすじ（無ければ blocked。S0 で書く）・採った人物・前の話までの構成
- 生成：k 個の構成を LLM に頼む
- 検査（プログラム）：ページの数が spec.structure.page_count と合うか、ページの番号が 1 から欠けずに並ぶか、
  見せ場と伏線のページがその話の中にあるか。外れたら落とす
- 観点ごとの判定（LLM）：spec.structure.views（頼む人が渡す観点の言葉）ごとに判定させ、指摘として出す。
  判定の精度は測っていないので候補は落とさない（未検証）
- 評価役は置かない。指摘の少ない案を初めの候補にする。人が採ると構成（EpisodeOutline）を採った人の操作として書く
"""

import hashlib
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from temporalio.exceptions import ApplicationError

from v3server.canonical_tables.harness_tables import EpisodeOutline, HarnessCandidate, HarnessUnit
from v3server.canonical_tables.material_and_setting_tables import WorkPlan
from v3server.canonical_tables.work_tree_tables import Episode
from v3server.database_engine import get_sessionmaker
from v3server.harness import queue_calls as q
from v3server.harness import stage_steps_common as c
from v3server.harness.upstream_versions import characters_by_name
from v3server.llm_questions.answer_json_reader import BrokenAnswerError
from v3server.llm_questions.structure_question import (
    build_structure_question,
    build_structure_views_question,
    outline_text,
    parse_structure_answer,
    parse_structure_views_answer,
)
from v3server.operations.material_and_plan_operations import SetEpisodeOutline
from v3server.operations.operation_submit_and_undo import submit


class StructureSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_count: int = Field(ge=1, le=400)
    # 構成を判定させる観点の言葉（空なら判定させない）
    views: list[str]


cut_out = c.cut_out_episode


async def earlier_outlines(session, work_id: str, episode: Episode) -> list[str]:
    rows = (await session.execute(
        select(Episode, EpisodeOutline).join(EpisodeOutline, EpisodeOutline.episode_id == Episode.id)
        .where(Episode.work_id == work_id, Episode.number < episode.number, Episode.removed.is_(False),
               EpisodeOutline.removed.is_(False)).order_by(Episode.number))).all()
    return [f"第{e.number}話：\n{outline_text(o.outline)}" for e, o in rows]


async def context(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    spec = c.spec_of(unit, "structure", StructureSpec)
    async with get_sessionmaker()() as session:
        await q.require_route(session, "structure")
        if spec.views:
            await q.require_route(session, "structure_views")
        plan = (await session.execute(select(WorkPlan).where(WorkPlan.work_id == unit.work_id))).scalar_one_or_none()
        if plan is None or not (plan.synopsis or "").strip():
            raise q.blocked("企画のあらすじが無い（S0 で書く）")
        ep = await session.get(Episode, unit.target_id)
        chars = await characters_by_name(session, unit.work_id)
        earlier = await earlier_outlines(session, unit.work_id, ep)
    question = build_structure_question(plan.synopsis, [(n, m.traits or "") for n, m in sorted(chars.items())],
                                        ep.number, spec.page_count, earlier, args.get("reject_reason"))
    return {"question": question, "cost": 0, "job_ids": []}


async def generate(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    return await c.ask_candidates(unit, args, "structure", args["context"]["question"],
                                  lambda t: parse_structure_answer(t).model_dump())


def shape_findings(outline: dict[str, Any], page_count: int) -> list[dict[str, Any]]:
    pages = [p["page"] for p in outline["pages"]]
    inside = set(range(1, page_count + 1))
    stray = sorted({*outline["highlights"], *(f["page"] for f in outline["foreshadow"])} - inside)
    return [
        c.finding("ページの数", len(pages) == page_count, True, f"{len(pages)} ページ（決めた数 {page_count}）"),
        c.finding("ページの番号", pages == sorted(inside), True,
                  "1 から欠けずに並ぶ" if pages == sorted(inside) else f"並び {pages}"),
        c.finding("見せ場・伏線のページ", not stray, True, "話の中" if not stray else f"話に無いページ {stray}"),
    ]


async def check(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    spec = c.spec_of(unit, "structure", StructureSpec)
    costs: list[str] = []

    async def judge(cand: HarnessCandidate) -> list[dict[str, Any]]:
        out = shape_findings(cand.content, spec.page_count)
        if not spec.views:
            return out + [c.finding("観点ごとの判定", None, False, "観点（spec.structure.views）が無いので判定させない")]
        question = build_structure_views_question(outline_text(cand.content), spec.views)
        key = f"{unit.id}:c{cand.id}:views:" + hashlib.sha256(question.encode()).hexdigest()[:12]
        text, jid = await q.ask_text(unit, key, "structure_views", q.user_message(question, []))
        costs.append(jid)
        try:
            judged = parse_structure_views_answer(text, spec.views)
        except BrokenAnswerError as e:
            raise ApplicationError(f"観点の判定の答えの形が崩れた: {e}", type="broken_response", non_retryable=True) from e
        return out + [c.finding(f"観点：{v.view}", v.ok, False, v.why, judge="llm") for v in judged]

    result = await c.check_candidates(unit, args, judge)
    async with get_sessionmaker()() as session:
        result["cost"] = await q.jobs_cost(session, costs)
    result["job_ids"] = costs
    return result


async def evaluate(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    return await c.pick_fewest_flags(unit, args, "指摘の少ない案（構成の評価役は置かない。観点の判定は指摘として出す）")


async def finalize(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    async with get_sessionmaker()() as session:
        cand = await c.picked_content(session, args)
        event = await submit(session, await q.authz(), c.human(args["by"]), unit.work_id,
                             SetEpisodeOutline(episode_id=unit.target_id, outline=cand.content))
        return {"candidate_id": cand.id, "event_id": event.id}


async def discard_round(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    return await c.discard_candidates(unit, args)
