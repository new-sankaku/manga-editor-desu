"""総合（S6）の作業の段。対象は話。ページと話の総合の判定を作り、人が見て完成とする（設計 5 の表）。

- 生成：ページを書き出しと同じ描き方で描き、黒の量・白さを測り、VLM にページごとの要約を書かせる（候補48）。
  構成（S1 の EpisodeOutline）があれば、要約と構成を比べて食い違いを挙げさせる。候補は1つ（同じページを何度測っても
  同じになるため。VLM の要約はぶれるが、くり返す回数を決める材料が無い。未検証）
- 検査（プログラム）：見開きの黒の割合（harness.overall.spread_black_max）と、ページの白の割合
  （harness.overall.page_white_max）。閾値が無ければ blocked。値は作品ごとに人が決める（7章。未検証）
- 指摘で候補は落とさない（候補は今の原稿を測った物で、落としても同じ物を測り直すだけ。直すのは人）
- 評価役は置かない。人が見て採る（完成）
"""

import base64
import hashlib
import io
from typing import Any

import numpy as np
from sqlalchemy import select
from temporalio.exceptions import ApplicationError

from v3server.canonical_tables.harness_tables import EpisodeOutline, HarnessUnit
from v3server.canonical_tables.work_tree_tables import Work
from v3server.database_engine import get_sessionmaker
from v3server.harness import queue_calls as q
from v3server.harness import stage_steps_common as c
from v3server.llm_questions.answer_json_reader import BrokenAnswerError
from v3server.llm_questions.overall_review_question import (
    build_outline_compare_question,
    build_page_summary_question,
    parse_outline_compare_answer,
    parse_page_summary_answer,
)
from v3server.llm_questions.structure_question import outline_text
from v3server.print_export.book_layout import episode_pages, page_sides
from v3server.print_export.export_runner import ExportRefused, render_page_preview

PREFIX = "harness.overall."
NEEDED = {"spread_black_max": "見開きの黒い画素の割合の上限（0〜1）", "page_white_max": "ページの白い画素の割合の上限（0〜1）"}
# 黒・白の割合を測るためにページを描く解像度。割合を見るだけなので、細い線が消えない程度の値（解像度による差は未検証）
PREVIEW_DPI = 72
# 黒・白と数える明るさの境（0〜255）。灰色のトーンをどちらにも数えないための境で、閾値ではない（未検証）
DARK, LIGHT = 64, 224

cut_out = c.cut_out_episode


async def context(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    async with get_sessionmaker()() as session:
        work = await session.get(Work, unit.work_id)
        if work.page_spec is None or work.first_page_is_left is None:
            raise q.blocked("作品の寸法（page_spec）と1ページ目の位置（first_page_is_left）がまだ決まっていない")
        await q.require_route(session, "page_summary")
        th = await c.thresholds_of(session, unit.work_id, PREFIX, NEEDED)
        outline = (await session.execute(select(EpisodeOutline).where(
            EpisodeOutline.episode_id == unit.target_id, EpisodeOutline.removed.is_(False)))).scalar_one_or_none()
        if outline is not None:
            await q.require_route(session, "outline_compare")
    return {"thresholds": th, "outline": outline.outline if outline else None, "cost": 0, "job_ids": []}


def _ratios(im) -> tuple[float, float]:
    g = np.asarray(im.convert("L"))
    return float((g < DARK).mean()), float((g > LIGHT).mean())


def _openings(count: int, first_page_is_left: bool, reading_direction: str) -> list[tuple[int, int]]:
    """見開きで並ぶページの組（並びの番号）。読む向きで前に来る側から始まる2ページ。"""
    sides = page_sides(count, first_page_is_left)
    first = "right" if reading_direction == "rtl" else "left"
    return [(i, i + 1) for i in range(count - 1) if sides[i] == first]


async def generate(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    ctx = args["context"]

    async def measure() -> dict[str, Any]:
        async with get_sessionmaker()() as session:
            work = await session.get(Work, unit.work_id)
            pages = await episode_pages(session, unit.target_id)
            images = []
            for p in pages:
                try:
                    images.append(await render_page_preview(session, work, p.id, PREVIEW_DPI))
                except ExportRefused as e:
                    raise q.blocked(f"ページ {p.number} を描けない: {e}") from e
            rd, first_left = work.reading_direction, work.first_page_is_left
        if not pages:
            raise q.blocked("話にページが無い")
        ratios = [_ratios(im) for im in images]
        rows = [{"page_id": p.id, "number": p.number, "black": b, "white": w} for p, (b, w) in zip(pages, ratios, strict=True)]
        openings = [{"pages": [pages[a].number, pages[b].number], "black": (ratios[a][0] + ratios[b][0]) / 2}
                    for a, b in _openings(len(pages), first_left, rd)]
        urls = []
        for im in images:
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            urls.append("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode())
        numbers = [p.number for p in pages]
        question = build_page_summary_question(numbers)
        key = f"{unit.id}:a{args['attempt']}:summary:" + hashlib.sha256("".join(urls).encode()).hexdigest()[:12]
        text, jid = await q.ask_text(unit, key, "page_summary", q.user_message(question, urls))
        job_ids = [jid]
        try:
            summaries = [(numbers[s.image - 1], s.summary) for s in parse_page_summary_answer(text, len(numbers))]
        except BrokenAnswerError as e:
            raise ApplicationError(f"ページの要約の答えの形が崩れた: {e}", type="broken_response",
                                   non_retryable=True) from e
        gaps = None
        if ctx["outline"] is not None:
            question = build_outline_compare_question(outline_text(ctx["outline"]), summaries)
            key = f"{unit.id}:a{args['attempt']}:compare:" + hashlib.sha256(question.encode()).hexdigest()[:12]
            text, jid = await q.ask_text(unit, key, "outline_compare", q.user_message(question, []))
            job_ids.append(jid)
            try:
                gaps = [g.model_dump() for g in parse_outline_compare_answer(text, set(numbers))]
            except BrokenAnswerError as e:
                raise ApplicationError(f"構成との比べの答えの形が崩れた: {e}", type="broken_response",
                                       non_retryable=True) from e
        async with get_sessionmaker()() as session:
            cost = await q.jobs_cost(session, job_ids)
        return {"pages": rows, "openings": openings, "summaries": [{"page": n, "summary": s} for n, s in summaries],
                "gaps": gaps, "cost": cost, "job_ids": job_ids}

    return await c.one_candidate(unit, args, measure, "今の原稿を測った物なので候補は1つ")


async def check(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    th = args["context"]["thresholds"]

    async def judge(cand) -> list[dict[str, Any]]:
        bmax, wmax = th["spread_black_max"], th["page_white_max"]
        out = []
        for o in cand.content["openings"]:
            out.append(c.finding(f"見開きの黒（{o['pages'][0]}・{o['pages'][1]}ページ）", o["black"] <= bmax["value"],
                                 False, f"{o['black']:.0%}（上限 {bmax['value']:.0%}、閾値は{bmax['status']}）"))
        for p in cand.content["pages"]:
            out.append(c.finding(f"ページの白（{p['number']}ページ）", p["white"] <= wmax["value"], False,
                                 f"{p['white']:.0%}（上限 {wmax['value']:.0%}、閾値は{wmax['status']}）"))
        gaps = cand.content["gaps"]
        if gaps is None:
            out.append(c.finding("構成との食い違い", None, False, "構成（S1）が無いので比べない"))
        else:
            out.append(c.finding("構成との食い違い", not gaps, False,
                                 "無い" if not gaps else "；".join(f"{g['page']}ページ：{g['why']}" for g in gaps),
                                 judge="llm"))
        return out

    return await c.check_candidates(unit, args, judge)


async def evaluate(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    return await c.pick_fewest_flags(unit, args, "今の原稿を測った候補は1つ")


async def finalize(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    return {"candidate_id": args["candidate_id"], "note": "人が総合の判定を見て完成とした"}


async def discard_round(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    return await c.discard_candidates(unit, args)
