"""設定資料（S2）の作業の段。対象は作品。登場人物と場所の文章と、絵を作る言葉を作る。

- 文脈：企画のあらすじ（無ければ blocked）・読者・構成（あれば）。spec.settings.document（取り込んだ原稿の文）が
  あれば、先に原稿から記憶を作らせ（imported_text_question の B 案）、記憶だけを資料に入れる。指示に見えた文は
  記憶に入れず、段の結果に残して人に見せる
- 生成：k 個の設定資料を LLM に頼む
- 検査（プログラム）：必須項目（名前・特徴・絵を作る言葉。答えの形で確かめる）、人物の数が決めた範囲か（外れたら落とす）、
  設定資料に同じ名前が既にあるか（指摘。採っても既にある名前は足さない）
- 見分け（LLM）：主要な人物を互いに見分けられるか。取り違えそうな組を指摘として出す（精度は未検証。落とさない）
- 参照の絵（画像生成）は作らない（未実装。人が設定資料の画面で絵を置く）
- 人が採ると、採った人の操作として設定資料を足す（人物は character、場所は background）
"""

import hashlib
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from temporalio.exceptions import ApplicationError

from v3server.canonical_tables.harness_tables import EpisodeOutline, HarnessUnit
from v3server.canonical_tables.material_and_setting_tables import MaterialEntry, WorkPlan
from v3server.canonical_tables.work_tree_tables import Episode
from v3server.database_engine import get_sessionmaker
from v3server.harness import queue_calls as q
from v3server.harness import stage_steps_common as c
from v3server.llm_questions.answer_json_reader import BrokenAnswerError
from v3server.llm_questions.imported_text_question import (
    build_memory_with_suspicious_question,
    parse_memory_with_suspicious_answer,
)
from v3server.llm_questions.settings_sheet_question import (
    build_distinguish_question,
    build_settings_sheet_question,
    parse_distinguish_answer,
    parse_settings_sheet_answer,
)
from v3server.llm_questions.structure_question import outline_text
from v3server.operations.material_and_plan_operations import AddMaterialEntry
from v3server.operations.operation_submit_and_undo import submit


class SettingsSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 絵を作る言葉の説明（渡す先のモデルが受け付ける言葉）
    model_description: str = Field(min_length=1)
    character_min: int = Field(ge=1, le=100)
    character_max: int = Field(ge=1, le=100)
    # 取り込んだ原稿の文（無ければ None）
    document: str | None

    @model_validator(mode="after")
    def _range(self) -> "SettingsSpec":
        if self.character_min > self.character_max:
            raise ValueError("character_min が character_max より大きい")
        return self


cut_out = c.cut_out_episode


async def _existing_names(session, work_id: str) -> set[str]:
    rows = (await session.execute(select(MaterialEntry.name).where(
        MaterialEntry.work_id == work_id, MaterialEntry.removed.is_(False),
        MaterialEntry.proposal_state != "rejected"))).scalars().all()
    return set(rows)


async def context(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    spec = c.spec_of(unit, "settings", SettingsSpec)
    async with get_sessionmaker()() as session:
        await q.require_route(session, "settings_sheet")
        await q.require_route(session, "distinguish")
        if spec.document:
            await q.require_route(session, "imported_text")
        plan = (await session.execute(select(WorkPlan).where(WorkPlan.work_id == unit.work_id))).scalar_one_or_none()
        if plan is None or not (plan.synopsis or "").strip():
            raise q.blocked("企画のあらすじが無い（S0 で書く）")
        rows = (await session.execute(
            select(Episode, EpisodeOutline).join(EpisodeOutline, EpisodeOutline.episode_id == Episode.id)
            .where(Episode.work_id == unit.work_id, Episode.removed.is_(False), EpisodeOutline.removed.is_(False))
            .order_by(Episode.number))).all()
        outlines = [f"第{e.number}話：\n{outline_text(o.outline)}" for e, o in rows]
    memory, suspicious, job_ids = [], [], []
    if spec.document:
        question = build_memory_with_suspicious_question(spec.document)
        key = f"{unit.id}:memory:" + hashlib.sha256(question.encode()).hexdigest()[:12]
        text, jid = await q.ask_text(unit, key, "imported_text", q.user_message(question, []))
        job_ids.append(jid)
        try:
            got = parse_memory_with_suspicious_answer(text)
        except BrokenAnswerError as e:
            raise ApplicationError(f"原稿の記憶の答えの形が崩れた: {e}", type="broken_response", non_retryable=True) from e
        memory, suspicious = [got.memory], got.suspicious
    question = build_settings_sheet_question(plan.synopsis, plan.audience, outlines, memory, spec.model_description,
                                             spec.character_min, spec.character_max, args.get("reject_reason"))
    async with get_sessionmaker()() as session:
        cost = await q.jobs_cost(session, job_ids)
    return {"question": question, "memory": memory, "suspicious": suspicious, "cost": cost, "job_ids": job_ids}


async def generate(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    return await c.ask_candidates(unit, args, "settings_sheet", args["context"]["question"],
                                  lambda t: parse_settings_sheet_answer(t).model_dump())


async def check(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    spec = c.spec_of(unit, "settings", SettingsSpec)
    asked: list[str] = []
    async with get_sessionmaker()() as session:
        existing = await _existing_names(session, unit.work_id)
    suspicious = args["context"].get("suspicious") or []

    async def judge(cand) -> list[dict[str, Any]]:
        chars = cand.content["characters"]
        n = len(chars)
        names = [x["name"] for x in chars] + [x["name"] for x in cand.content["locations"]]
        same = sorted(set(names) & existing)
        out = [
            c.finding("人物の数", spec.character_min <= n <= spec.character_max, True,
                      f"{n} 人（{spec.character_min}〜{spec.character_max}）"),
            c.finding("設定資料に同じ名前", not same, False,
                      "無い" if not same else f"既にある：{'、'.join(same)}（採っても足さない）"),
            c.finding("原稿の中の指示に見えた文", not suspicious, False,
                      "無い" if not suspicious else "記憶に入れなかった：" + "／".join(suspicious)),
        ]
        if n < 2:
            return out + [c.finding("見分け", None, False, "人物が1人なので比べない")]
        question = build_distinguish_question([(x["name"], x["traits"]) for x in chars])
        key = f"{unit.id}:c{cand.id}:distinguish:" + hashlib.sha256(question.encode()).hexdigest()[:12]
        text, jid = await q.ask_text(unit, key, "distinguish", q.user_message(question, []))
        asked.append(jid)
        try:
            pairs = parse_distinguish_answer(text, {x["name"] for x in chars})
        except BrokenAnswerError as e:
            raise ApplicationError(f"見分けの答えの形が崩れた: {e}", type="broken_response", non_retryable=True) from e
        return out + [c.finding("見分け", not pairs, False,
                                "取り違えそうな組は無い" if not pairs
                                else "；".join(f"{p.a} と {p.b}：{p.why}" for p in pairs), judge="llm")]

    result = await c.check_candidates(unit, args, judge)
    async with get_sessionmaker()() as session:
        result["cost"] = await q.jobs_cost(session, asked)
    result["job_ids"] = asked
    return result


async def evaluate(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    return await c.pick_fewest_flags(unit, args, "指摘の少ない案（設定資料の評価役は置かない。見分けの判定は指摘として出す）")


async def finalize(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    async with get_sessionmaker()() as session:
        cand = await c.picked_content(session, args)
        existing = await _existing_names(session, unit.work_id)
        added, skipped = [], []
        authz, who = await q.authz(), c.human(args["by"])
        rows = ([("character", x["name"], x["traits"], x["role"], x["prompt"]) for x in cand.content["characters"]]
                + [("background", x["name"], x["traits"], None, x["prompt"]) for x in cand.content["locations"]])
        for kind, name, traits, role, prompt in rows:
            if name in existing:
                skipped.append(name)
                continue
            op = AddMaterialEntry(kind=kind, name=name, traits=traits, notes=role or None,
                                  generation={"prompt": prompt}, job_id=cand.job_id)
            await submit(session, authz, who, unit.work_id, op)
            added.append({"id": op.id, "name": name, "kind": kind})
        return {"candidate_id": cand.id, "added": added, "skipped_existing": skipped}


async def discard_round(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    return await c.discard_candidates(unit, args)
