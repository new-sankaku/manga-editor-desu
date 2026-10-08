"""仕上げ（S5）の作業の段。対象は話。人だけが置く工程（設計 5 の表：プログラム中心）。

吹き出し・文字・擬音の置き場は人が置く。AIは置かない（生成の段は、人が置いた今の状態を候補の中身として写すだけで、
LLM・画像生成を呼ばない）。プログラムと検出器・VLM は検査だけをする。

- 検査（プログラム）：ネームの検査（6章。内側の枠・吹き出しの順・交差・しっぽの向き・文字数など）を今の話に当てる。
  閾値が無い検査があれば blocked
- 検査（検出器）：絵のあるコマで、顔が吹き出しに隠れる割合（p47）。閾値は作画と同じ harness.drawing.face_covered_max
  （コマの絵がコマの枠いっぱいに置かれているとして比べる。絵の置き方 image_placement は見ない。未検証）
- 検査（VLM）：コマの枠だけを描いた絵から読む順を判定させ（p11・p45）、コマの順と比べる
- どの指摘でも候補は落とさない（直すのは人。落とすと同じ物を写し直すだけになる）。人が見て採る（完成条件に
  human_approve が無ければ、検査が通った所で終わる）
"""

import base64
import hashlib
import io
from typing import Any

from PIL import Image, ImageDraw
from sqlalchemy import select
from temporalio.exceptions import ApplicationError

from v3server.canonical_tables.harness_tables import HarnessUnit
from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.text_and_layer_tables import TextItem
from v3server.canonical_tables.work_tree_tables import Page, Panel, Work
from v3server.database_engine import get_sessionmaker
from v3server.harness import queue_calls as q
from v3server.harness import stage_steps_common as c
from v3server.harness.panel_drawing_steps import _require, _xyxy, covered_ratio, drawing_thresholds, text_boxes_mm
from v3server.http_routes.name_check_routes import name_check_thresholds
from v3server.image_file_storage import read_image
from v3server.llm_questions.answer_json_reader import BrokenAnswerError
from v3server.llm_questions.reading_order_question import (
    assign_points_to_panels,
    build_reading_order_question,
    parse_reading_order_answer,
)
from v3server.name_checks.name_check_runner import run_name_checks
from v3server.operations.image_placement_carry import frame_bbox
from v3server.operations.name_draft_conversion import READING_DIRECTION, name_draft_of_episode

# 読む順の判定に渡す絵の、1mm あたりの画素（枠の線が見える大きさ。精度との関係は未検証）
FRAME_IMAGE_PX_PER_MM = 4

cut_out = c.cut_out_episode


async def _pages(session, episode_id: str) -> list[Page]:
    return (await session.execute(select(Page).where(Page.episode_id == episode_id, Page.removed.is_(False))
                                  .order_by(Page.number))).scalars().all()


async def _panels(session, page_id: str) -> list[Panel]:
    return (await session.execute(select(Panel).where(Panel.page_id == page_id, Panel.removed.is_(False))
                                  .order_by(Panel.order))).scalars().all()


async def context(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    async with get_sessionmaker()() as session:
        work = await session.get(Work, unit.work_id)
        if work.page_spec is None:
            raise q.blocked("作品の寸法（page_spec）がまだ決まっていない")
        await q.require_route(session, "reading_order")
    return {"cost": 0, "job_ids": []}


async def generate(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    async def snapshot() -> dict[str, Any]:
        async with get_sessionmaker()() as session:
            pages = []
            for p in await _pages(session, unit.target_id):
                texts = (await session.execute(select(TextItem).where(
                    TextItem.page_id == p.id, TextItem.removed.is_(False)))).scalars().all()
                panels = await _panels(session, p.id)
                placed = sum(1 for t in texts if t.box_mm)
                pages.append({"page_id": p.id, "number": p.number, "texts": len(texts), "balloons_placed": placed,
                              "panels": len(panels), "with_image": sum(1 for x in panels if x.image_id)})
        if not any(p["texts"] or p["balloons_placed"] for p in pages):
            raise q.blocked("吹き出し・文字がまだ置かれていない。仕上げは人が置く工程なので、置いてから再開する")
        return {"pages": pages, "by": "人が置いた今の状態（AIは置かない）"}

    return await c.one_candidate(unit, args, snapshot, "仕上げは人が置く工程。候補は人が置いた今の状態の1つだけ")


def frame_image(panels: list[Panel], width_mm: float, height_mm: float) -> str:
    k = FRAME_IMAGE_PX_PER_MM
    im = Image.new("RGB", (int(width_mm * k), int(height_mm * k)), "white")
    d = ImageDraw.Draw(im)
    for p in panels:
        pts = [(x * k, y * k) for x, y in (p.frame or {}).get("polygon_mm") or []]
        if len(pts) >= 3:
            d.polygon(pts, outline="black", width=max(1, k // 2))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


async def _reading_order(unit: HarnessUnit, work: Work, page: Page, panels: list[Panel]) -> tuple[dict[str, Any], str]:
    spec = work.page_spec
    # コマの枠は基本枠の左上が原点（PageSpec）。絵も基本枠の大きさで描く
    w, h = float(spec["frame_width_mm"]), float(spec["frame_height_mm"])
    framed = [p for p in panels if frame_bbox(p.frame)]
    slanted = any(len((p.frame or {}).get("polygon_mm") or []) != 4 for p in framed)
    question = build_reading_order_question(READING_DIRECTION[work.reading_direction], w, h, slanted)
    image = frame_image(framed, w, h)
    key = f"{unit.id}:order:{page.id}:" + hashlib.sha256((question + image).encode()).hexdigest()[:12]
    text, jid = await q.ask_text(unit, key, "reading_order", q.user_message(question, [image]), page.id)
    centers = {}
    for i, p in enumerate(framed):
        x0, y0, x1, y1 = frame_bbox(p.frame)
        centers[i] = ((x0 + x1) / 2, (y0 + y1) / 2)
    try:
        got = assign_points_to_panels(parse_reading_order_answer(text), centers, text)
    except BrokenAnswerError as e:
        raise ApplicationError(f"読む順の答えの形が崩れた: {e}", type="broken_response", non_retryable=True) from e
    want = list(range(len(framed)))
    return (c.finding(f"読む順（{page.number}ページ）", got == want, False,
                      "コマの順と同じ" if got == want else f"判定の順 {[g + 1 for g in got]}（コマの順 1〜{len(want)}）",
                      judge="llm"), jid)


async def _face_overlap(unit: HarnessUnit, page: Page, panels: list[Panel], th: dict[str, Any]
                        ) -> tuple[list[dict[str, Any]], list[str]]:
    out, jobs = [], []
    for p in panels:
        async with get_sessionmaker()() as session:
            balloons = await text_boxes_mm(session, p.id)
        if not (p.image_id and balloons and p.content.get("people")):
            continue
        _require(th, ["face_covered_max"])
        async with get_sessionmaker()() as session:
            img = await session.get(ImageFile, p.image_id)
            process = await q.require_route(session, "detect_person")
            job = await q.ensure_job(session, unit, f"{unit.id}:face:{p.id}:{img.id}", process, {
                "endpoint": "/person_face_head", "images": {"image": img.sha256},
                "form": {"edge_px": int(th["edge_px"]["value"]), "score_threshold": th["person_score"]["value"]}},
                page.id)
            jid = job.id
        (job,) = await q.wait_jobs(unit.id, [jid])
        jobs.append(jid)
        if job.status != "done":
            raise q.job_failure(job)
        with Image.open(io.BytesIO(read_image(img.sha256))) as im:
            W, H = im.size
        fx0, fy0, fx1, fy1 = frame_bbox(p.frame)
        bpx = [[(b[0] - fx0) / (fx1 - fx0) * W, (b[1] - fy0) / (fy1 - fy0) * H, (b[2] - fx0) / (fx1 - fx0) * W,
                (b[3] - fy0) / (fy1 - fy0) * H] for b in balloons]
        faces = job.result.get("faces", [])
        worst = max((covered_ratio(_xyxy(f), bpx) for f in faces), default=0.0)
        hi = th["face_covered_max"]["value"]
        out.append(c.finding(f"顔と吹き出しの重なり（{page.number}ページ {p.order}コマ）", worst <= hi, False,
                             f"いちばん隠れた顔 {worst:.0%}（上限 {hi:.0%}、閾値は{th['face_covered_max']['status']}）。"
                             f"顔の検出 {len(faces)}"))
    return out, jobs


async def check(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    jobs: list[str] = []

    async def judge(cand) -> list[dict[str, Any]]:
        async with get_sessionmaker()() as session:
            work = await session.get(Work, unit.work_id)
            draft = await name_draft_of_episode(session, work, unit.target_id)
            values, used = await name_check_thresholds(session, unit.work_id)
            report = run_name_checks(draft, values)
            unset = [r.threshold_key or r.check_id for r in report.results if r.status == "閾値未設定"]
            if unset:
                raise q.blocked("ネームの検査の閾値が未設定: " + "、".join(unset), missing=unset)
            pages = [(pg, await _panels(session, pg.id)) for pg in await _pages(session, unit.target_id)]
            th = await drawing_thresholds(session, unit.work_id)
        out = [c.finding(r.title, None if r.status == "データなし" else r.status == "合格", False,
                         "；".join(r.report_lines()[:3]),
                         threshold_status=used.get(r.threshold_key, {}).get("status") if r.threshold_key else None)
               for r in report.results]
        for pg, panels in pages:
            if panels:
                f, jid = await _reading_order(unit, work, pg, panels)
                out.append(f)
                jobs.append(jid)
            found, js = await _face_overlap(unit, pg, panels, th)
            out += found
            jobs.extend(js)
        return out

    result = await c.check_candidates(unit, args, judge)
    async with get_sessionmaker()() as session:
        result["cost"] = await q.jobs_cost(session, jobs)
    result["job_ids"] = jobs
    return result


async def evaluate(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    return await c.pick_fewest_flags(unit, args, "候補は人が置いた今の状態の1つだけ")


async def finalize(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    """人が置いた物はもう正本にある。採ったことを記録するだけ。"""
    return {"candidate_id": args["candidate_id"], "note": "仕上げは人が置いた物を正本のまま使う"}


async def discard_round(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    return await c.discard_candidates(unit, args)
