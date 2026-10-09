"""企画の聞き取り（S0）の作業の段。対象は作品（企画は作品に1つ）。設計 5.2。

- 文脈：人の最初の要望（spec.plan.request）・今の企画・これまでの人の答えから問いを組む
- 生成：k 個の答えを LLM に頼む。答えは「人への質問」と「企画の案」のどちらか、または両方
- 検査（プログラム）：必須項目（spec.plan.required_fields。頼む人が決める）がそろっているか。そろっていない案は、
  質問があれば指摘だけ（人が答える）、質問も無ければ落とす
- 評価モデルは置かない（企画の良し悪しの判定器は無い）。指摘の少ない案を初めの候補にする
- 人：質問に答える（review の answer）か、案を採る。採ると、採った人の操作として企画を書く（ネームの案を採るのと
  同じ。人が中身を見て決めた物なので手動編集の印が付く）。必須項目のそろわない案は採れない（口で断る）
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from v3server.canonical_tables.harness_tables import HarnessCandidate, HarnessUnit
from v3server.canonical_tables.material_and_setting_tables import WorkPlan
from v3server.database_engine import get_sessionmaker
from v3server.harness import queue_calls as q
from v3server.harness import stage_steps_common as c
from v3server.llm_questions.plan_interview_question import (
    PLAN_FIELDS,
    PlanDraft,
    build_plan_interview_question,
    missing_fields,
    parse_plan_interview_answer,
)
from v3server.messages import m, ms, render
from v3server.operations.material_and_plan_operations import SetWorkPlan
from v3server.operations.operation_submit_and_undo import submit


class PlanSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 人の最初の要望（作業役はここから質問を始める）
    request: str = Field(min_length=1)
    # そろうまで採れない項目
    required_fields: list[Literal["synopsis", "audience", "exclusions", "notes"]] = Field(min_length=1)


# 作業役が人へ質問を返す種類。答え（review の answer）を次の回の文脈に入れる
TAKES_ANSWERS = True
# 検査の指摘に出す項目の名前。問いの中の名前（PLAN_FIELDS。LLM へ送る日本語）と同じ言葉を、画面の言語で出せる形で持つ。
# 「入れないもの」は、生成の欄の名前（image_process_registry.py。訳は Negative prompt）と日本語が同じで意味が違う。
# 辞書は日本語の文の形で引くので、文の形を分けてある（値 plan は空。日本語で出す文は同じ）
FIELD_LABELS = {"synopsis": ms("あらすじ"), "audience": ms("読者"), "exclusions": ms("入れないもの{plan}", plan=""),
                "notes": ms("メモ")}

cut_out = c.cut_out_episode


async def _plan(session, work_id: str) -> dict[str, Any]:
    plan = (await session.execute(select(WorkPlan).where(WorkPlan.work_id == work_id))).scalar_one_or_none()
    return {k: getattr(plan, k) for k in PLAN_FIELDS} if plan else {}


async def context(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    spec = c.spec_of(unit, "plan", PlanSpec)
    async with get_sessionmaker()() as session:
        await q.require_route(session, "plan_interview")
        current = await _plan(session, unit.work_id)
    answers = list(args.get("answers") or [])
    if args.get("reject_reason"):
        answers.append(f"（前の案への指摘）{args['reject_reason']}")  # i18n:prompt
    question = build_plan_interview_question(spec.request, current, answers, list(spec.required_fields))
    return {"question": question, "answers": answers, "cost": 0, "job_ids": []}


async def generate(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    return await c.ask_candidates(unit, args, "plan_interview", args["context"]["question"],
                                  lambda t: parse_plan_interview_answer(t).model_dump())


async def check(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    spec = c.spec_of(unit, "plan", PlanSpec)

    async def judge(cand: HarnessCandidate) -> list[dict[str, Any]]:
        plan = PlanDraft.model_validate(cand.content["plan"]) if cand.content["plan"] else None
        questions = cand.content["questions"]
        missing = missing_fields(plan, list(spec.required_fields))
        return [
            c.finding(ms("必須項目"), not missing, drops=not questions,
                      detail=(ms("そろっている") if not missing
                              else ms("無い：{fields}", fields=[FIELD_LABELS[k] for k in missing]))),
            c.finding(ms("作者への質問"), not questions, drops=False,
                      detail=(ms("質問 {n} 件。答える（answer）と次の回に入る", n=len(questions)) if questions
                              else ms("質問 {n} 件", n=len(questions)))),
        ]

    return await c.check_candidates(unit, args, judge)


async def evaluate(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    return await c.pick_fewest_flags(unit, args, ms("指摘の少ない案（企画の評価モデルは置かない）"))


def not_approvable(cand: HarnessCandidate) -> str | None:
    content = cand.content or {}
    if not content.get("plan"):
        return m("企画の案の無い候補（質問だけ）は採れない。質問に答える（answer）")
    # 指摘の名前は包んだ文で入っている（前に作った候補は日本語の文のまま）。どちらも日本語の文に戻して比べる
    if any(render(f["name"], "ja") == "必須項目" and f["ok"] is False  # i18n:data
           for f in (cand.check or {}).get("findings", [])):
        return m("必須項目のそろわない案は採れない。質問に答えるか却下して作り直す")
    return None


async def finalize(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    async with get_sessionmaker()() as session:
        cand = await c.picked_content(session, args)
        values = {k: v for k, v in cand.content["plan"].items() if v not in (None, "", [])}
        op = SetWorkPlan(**values)
        event = await submit(session, await q.authz(), c.human(args["by"]), unit.work_id, op)
        return {"candidate_id": cand.id, "written": sorted(values), "event_id": event.id}


async def discard_round(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    return await c.discard_candidates(unit, args)
