"""作画（S4）の1コマの作業の段（設計 8.1・8.2）。作業の流れ（unit_workflow.py）が段ごとに活動として呼ぶ。

- 文脈：固定の部分（設定資料の人物の生成の言葉・作品の絵の言葉）はプログラムが組み、コマごとに変わる部分（タグ）だけを
  LLM に作らせる（redo_instruction_question。却下の理由があれば作り直しの問いに入れる）。大きさはコマの枠の縦横比から決める
- 生成：k 枚を、今の順番待ちに1枚ずつ頼む（image_process_registry の text_to_image。人が直した絵から続けるときは
  image_to_image で、人の手の範囲は今の仕組み（protected_mask_input）で貼り戻す）
- 検査：大きさ（プログラム）・人数と見切れ（検出器）・絵の中の文字（検出器）・写す範囲と角度（VLM）。手段の無い観点
  （背景・視線・ぼやけ・服と小物）は「判定できない」として必ず判断待ちに出す（設計 8.2 の最後）
- 評価：落ちなかった候補から、評価役（candidate_pick）に eval_repeats 回選ばせる。答えが割れたら「割れた」
- 確定：人の採用で、操作の窓口（AdoptImage）を人の操作として通す

閾値は作品の Threshold の表の harness.drawing.* の行を読む。設計に初めの値が無いので、無ければ作業は blocked で止め、
画面と確認待ち一覧に「閾値未設定」と出す（黙って通さない）。status=unverified（仮）の閾値で外れた候補は落とさず指摘だけ、
verified（確定）で外れたら落とす（設計 7.1）。rejected の行は無いものとして扱う。
"""

import math
import os
import tempfile
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from v3server.canonical_tables.harness_tables import HarnessCandidate, HarnessUnit
from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.threshold_and_finding_tables import Threshold
from v3server.canonical_tables.work_tree_tables import Panel
from v3server.database_engine import get_sessionmaker
from v3server.generation_queue.image_process_registry import spec_for
from v3server.harness import queue_calls as q
from v3server.harness.upstream_versions import (
    DRAWING_THRESHOLD_PREFIX,
    characters_by_name,
    panel_people_names,
)
from v3server.image_file_storage import read_image
from v3server.judge_procedures.candidate_pick import pick_candidate
from v3server.llm_questions.answer_json_reader import BrokenAnswerError
from v3server.llm_questions.redo_instruction_question import (
    build_first_tags_question,
    build_redo_tags_question,
    parse_tags_answer,
)
from v3server.llm_questions.shot_angle_question import build_shot_angle_question, parse_shot_angle_answer
from v3server.operations.image_candidate_operations import AdoptImage, SetImageDiscarded
from v3server.operations.image_placement_carry import frame_bbox
from v3server.operations.operation_submit_and_undo import submit
from v3server.request_actor import Actor
from temporalio.exceptions import ApplicationError

# 作画の検査が読む閾値（値の形は {"value": 数}）
THRESHOLDS = {
    "person_score": "人物の検出の score の下限",
    "edge_px": "見切れとみなす、枠が絵の端から何画素以内か",
    "text_score": "絵の中の文字の検出の score の下限",
}
# 手段が無く、人の確認に回す観点（設計 8.2）
HUMAN_ONLY_VIEWS = ("背景", "視線", "ぼやけ・線の潰れ", "服・アクセサリー・小物")


class DrawingSpec(BaseModel):
    """作画の作業の中身の決めごと。作業を頼む人が渡す（設計 8.1 の固定の部分のうち、人物以外）。"""

    model_config = ConfigDict(extra="forbid")

    # 渡す先のモデルが受け付ける言葉の説明（タグを作らせる問いに入れる）
    model_description: str = Field(min_length=1)
    quality_words: str
    style_words: str
    negative_words: str
    # 長い辺の画素（コマの縦横比で短い辺を決める。8の倍数に丸める）
    long_side: int = Field(ge=64, le=4096)
    # 処理の引数のうち、文・大きさ以外（形の指定など。処理の形でそのまま確かめる）
    base_params: dict[str, Any]
    # 人が直した絵から続けるときの、変える強さなど（image_to_image の引数のうち文・大きさ以外）
    redraw_params: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _params_fit(self) -> "DrawingSpec":
        """処理の引数の形を、頼む前（工程を始めるとき）に確かめる。文と大きさは作業が入れるので仮の値で見る。"""
        text = {"prompt": "x", "negative_prompt": ""}
        spec_for("text_to_image").params_model.model_validate({**self.base_params, **text, "width": 64, "height": 64})
        if self.redraw_params is not None:
            spec_for("image_to_image").params_model.model_validate({**self.redraw_params, **text})
        return self


def size_for_frame(frame: dict[str, Any] | None, long_side: int) -> tuple[int, int]:
    box = frame_bbox(frame)
    if box is None:
        raise q.blocked("コマの枠が無い。ネームで枠を決めてから作画する")
    w, h = box[2] - box[0], box[3] - box[1]
    if w <= 0 or h <= 0:
        raise q.blocked("コマの枠の大きさが0")
    if w >= h:
        return long_side // 8 * 8, max(64, math.floor(long_side * h / w / 8) * 8)
    return max(64, math.floor(long_side * w / h / 8) * 8), long_side // 8 * 8


async def drawing_thresholds(session, work_id: str) -> dict[str, dict[str, Any]]:
    """{名前: {value, status, source}}。足りなければ blocked。"""
    rows = (await session.execute(select(Threshold).where(
        Threshold.work_id == work_id, Threshold.key.like(DRAWING_THRESHOLD_PREFIX + "%")))).scalars().all()
    got = {t.key[len(DRAWING_THRESHOLD_PREFIX):]: t for t in rows if t.status != "rejected"}
    missing = [k for k in THRESHOLDS if k not in got]
    if missing:
        raise q.blocked("作画の検査の閾値が未設定: " + "、".join(f"{DRAWING_THRESHOLD_PREFIX}{k}（{THRESHOLDS[k]}）"
                                                     for k in missing), missing=[DRAWING_THRESHOLD_PREFIX + k
                                                                                 for k in missing])
    return {k: {"value": float(t.value["value"]), "status": t.status, "source": t.source} for k, t in got.items()}


def panel_description(panel: Panel) -> str:
    c = panel.content
    parts = []
    if c.get("content"):
        parts.append(f"中身：{c['content']}")
    for key, title in (("shot", "写す範囲"), ("angle", "角度"), ("background", "背景"), ("location", "場所")):
        if c.get(key):
            parts.append(f"{title}：{c[key]}")
    people = c.get("people") or []
    if people:
        parts.append("人物：" + "、".join(f"{p.get('name')}（顔の大きさ {p.get('face')}・向き {p.get('facing')}）"
                                         for p in people))
    else:
        parts.append("人物：なし")
    return "\n".join(parts)


# ---------------------------------------------------------------- 段


async def cut_out(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    async with get_sessionmaker()() as session:
        panel = await session.get(Panel, unit.target_id)
        if panel is None or panel.removed:
            raise ApplicationError("コマが無い（消された）", type="refused", non_retryable=True)
        if panel.human_confirmed:
            raise ApplicationError("人の確定印のあるコマは、AIが作り直さない（設計 9.2）", type="refused",
                                   non_retryable=True)
        DrawingSpec.model_validate(unit.spec.get("drawing"))
        return {"panel_id": panel.id, "page_id": panel.page_id, "people": panel_people_names(panel)}


async def context(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    """args: attempt, reject_reason, previous_tags, restart（文脈を捨てて出直す）, edit_image_id"""
    spec = DrawingSpec.model_validate(unit.spec["drawing"])
    async with get_sessionmaker()() as session:
        panel = await session.get(Panel, unit.target_id)
        thresholds = await drawing_thresholds(session, unit.work_id)
        await q.require_route(session, "panel_tags")
        await q.require_route(session, "detect_person")
        await q.require_route(session, "detect_text")
        await q.require_route(session, "shot_angle")
        await q.require_route(session, "pick")
        width, height = size_for_frame(panel.frame, spec.long_side)
        chars = await characters_by_name(session, unit.work_id)
        fixed, negative = [], [spec.negative_words]
        for name in panel_people_names(panel):
            m = chars.get(name)
            if m is None:
                raise q.blocked(f"設定資料に人物 {name} が無い（採った人物だけを使う）", character=name)
            prompt = (m.generation or {}).get("prompt")
            if not prompt:
                raise q.blocked(f"設定資料の人物 {name} に生成の言葉（generation.prompt）が無い。特徴の言葉は毎回全部入れる"
                                "（試作 p17）ので、人が設定資料に書く", character=name)
            fixed.append(prompt)
            if (m.generation or {}).get("negative_prompt"):
                negative.append(m.generation["negative_prompt"])
        description = panel_description(panel)
    previous = args.get("previous_tags") or []
    reason = args.get("reject_reason")
    if previous and not args.get("restart"):
        question = build_redo_tags_question(description, spec.model_description, previous, reason)
        asked = "redo"
    else:
        question = build_first_tags_question(description, spec.model_description)
        asked = "first"
    key = f"{unit.id}:a{args['attempt']}:panel_tags"
    text, job_id = await q.ask_text(unit, key, "panel_tags", q.user_message(question, []), unit.page_id)
    try:
        tags = parse_tags_answer(text)
    except BrokenAnswerError as e:
        raise ApplicationError(f"タグの答えの形が崩れた: {e}", type="broken_response", non_retryable=True) from e
    prompt = ", ".join(p.strip() for p in [spec.quality_words, spec.style_words, *fixed, ", ".join(tags)] if p.strip())
    async with get_sessionmaker()() as session:
        cost = await q.jobs_cost(session, [job_id])
    return {"prompt": prompt, "negative_prompt": ", ".join(n for n in negative if n.strip()), "width": width,
            "height": height, "tags": tags, "asked": asked, "thresholds": thresholds, "cost": cost,
            "job_ids": [job_id]}


async def generate(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    """args: attempt, context（文脈の段の答え）, edit_image_id（人が直した絵から続けるとき）"""
    spec = DrawingSpec.model_validate(unit.spec["drawing"])
    ctx, attempt, k = args["context"], args["attempt"], unit.limits["candidates_per_attempt"]
    source = args.get("edit_image_id")
    process = "image_to_image" if source else "text_to_image"
    if source and spec.redraw_params is None:
        raise q.blocked("人が直した絵から続けるには、作業の決めごとに redraw_params（image_to_image の引数）が要る")
    base = spec.redraw_params if source else spec.base_params
    params = {**base, "prompt": ctx["prompt"], "negative_prompt": ctx["negative_prompt"]}
    if not source:
        params.update(width=ctx["width"], height=ctx["height"])
    job_ids, cand_ids = [], []
    async with get_sessionmaker()() as session:
        panel = await session.get(Panel, unit.target_id)
        for i in range(k):
            hkey = f"{unit.id}:a{attempt}:gen{i}"
            cand = (await session.execute(select(HarnessCandidate).where(
                HarnessCandidate.harness_key == hkey))).scalar_one_or_none()
            if cand is None:
                cand = HarnessCandidate(unit_id=unit.id, attempt=attempt, k_index=i, harness_key=hkey,
                                        seed=args["seeds"][i], prompt=ctx["prompt"], status="requested", picked=False)
                session.add(cand)
                await session.commit()
            elif cand.status == "cancelled":
                # 人が今すぐ止めた段を再開した。同じ候補で頼み直す（ensure_job が新しい依頼を作る）
                cand.status, cand.dropped_reason = "requested", None
            request: dict[str, Any] = {
                "image_process": {"name": process, "params": params, "seed": cand.seed,
                                  "candidate_set_id": f"{unit.id}a{attempt}"[:32], "requested_params": params},
                "register": {"role": "panel_art", "page_id": panel.page_id, "panel_id": panel.id},
                # 進み具合の鍵は候補の id（画面は候補ごとに段数と途中の絵を出す）
                "progress_key": cand.id,
            }
            if source:
                request["input_images"] = [{"node": "source", "input": "image", "image_id": source,
                                            "purpose": "source"}]
                request["protected_mask_input"] = {"node": "protected_mask", "input": "image"}
            job = await q.ensure_job(session, unit, hkey, process, request, panel.page_id)
            cand.job_id = job.id
            await session.commit()
            job_ids.append(job.id)
            cand_ids.append(cand.id)
    jobs = await q.wait_jobs(unit.id, job_ids)
    out = []
    async with get_sessionmaker()() as session:
        for cid, job in zip(cand_ids, jobs):
            cand = await session.get(HarnessCandidate, cid)
            if job.status == "done" and job.result.get("registered"):
                cand.image_id, cand.status = job.result["registered"][0]["image_id"], "generated"
            else:
                cand.status = "failed" if job.status == "stopped" else "cancelled"
                cand.dropped_reason = f"生成が止まった（{job.failure_kind}）: {job.failure_detail}"
            out.append({"candidate_id": cid, "image_id": cand.image_id, "status": cand.status,
                        "failure_kind": job.failure_kind})
        cost = await q.jobs_cost(session, job_ids)
        await session.commit()
    refused = [o for o in out if o["failure_kind"] == "refused"]
    if refused and len(refused) == len(out):
        raise ApplicationError(f"生成が全部断られた: {jobs[0].failure_detail}", type="refused", non_retryable=True)
    if not any(o["image_id"] for o in out):
        raise ApplicationError("生成が全部止まった", {"kinds": [o["failure_kind"] for o in out]},
                               type="generation_failed", non_retryable=True)
    return {"candidates": out, "cost": cost, "job_ids": job_ids}


def _finding(name: str, ok: bool | None, threshold: dict[str, Any] | None, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": ok, "threshold_status": threshold["status"] if threshold else None, "detail": detail}


def verdict_of(findings: list[dict[str, Any]]) -> str:
    """落とすのは、確定の閾値か閾値の要らない検査で外れたときだけ。仮の閾値・VLM の比較で外れたら指摘（flag）。"""
    failed = [f for f in findings if f["ok"] is False]
    if any(f["threshold_status"] in (None, "verified") and f.get("drop", True) for f in failed):
        return "drop"
    if failed:
        return "flag"
    return "pass"


async def check(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    """args: attempt, context"""
    ctx, attempt = args["context"], args["attempt"]
    th = ctx["thresholds"]
    async with get_sessionmaker()() as session:
        panel = await session.get(Panel, unit.target_id)
        cands = (await session.execute(select(HarnessCandidate).where(
            HarnessCandidate.unit_id == unit.id, HarnessCandidate.attempt == attempt,
            HarnessCandidate.image_id.is_not(None)).order_by(HarnessCandidate.k_index))).scalars().all()
        imgs = {c.id: await session.get(ImageFile, c.image_id) for c in cands}
        want_people = len(panel.content.get("people") or [])
        want_shot, want_angle = panel.content.get("shot"), panel.content.get("angle")
        cand_ids = [c.id for c in cands]
        urls = [await q.image_data_url(session, c.image_id) for c in cands]
    job_ids: list[str] = []
    findings: dict[str, list[dict[str, Any]]] = {cid: [] for cid in cand_ids}
    # 大きさ（閾値の要らない検査）
    for cid in cand_ids:
        img = imgs[cid]
        if args.get("edit_image_id") is None:
            ok = (img.width, img.height) == (ctx["width"], ctx["height"])
            findings[cid].append(_finding("大きさ", ok, None, f"{img.width}x{img.height}（頼んだ {ctx['width']}x{ctx['height']}）"))
    # 検出器（人数・見切れ・文字）
    for cid in cand_ids:
        img = imgs[cid]
        async with get_sessionmaker()() as session:
            process = await q.require_route(session, "detect_person")
            job = await q.ensure_job(session, unit, f"{cid}:detect_person", process, {
                "endpoint": "/person_face_head", "images": {"image": img.sha256},
                "form": {"edge_px": int(th["edge_px"]["value"]), "score_threshold": th["person_score"]["value"]}},
                unit.page_id)
            pj = job.id
            process = await q.require_route(session, "detect_text")
            job = await q.ensure_job(session, unit, f"{cid}:detect_text", process, {
                "endpoint": "/text_regions", "images": {"image": img.sha256},
                "form": {"score_threshold": th["text_score"]["value"]}}, unit.page_id)
            tj = job.id
        pjob, tjob = await q.wait_jobs(unit.id, [pj, tj])
        job_ids += [pj, tj]
        for j in (pjob, tjob):
            if j.status != "done":
                raise q.job_failure(j)
        persons = pjob.result.get("persons", [])
        findings[cid].append(_finding("人数", len(persons) == want_people, th["person_score"],
                                      f"検出 {len(persons)} 人・ネーム {want_people} 人"))
        touching = [p["touch"] for p in persons if p.get("touch")]
        findings[cid].append({**_finding("見切れ", not touching, th["edge_px"],
                                         f"端に接した人物 {len(touching)}（{','.join(touching)}）"), "drop": False})
        texts = tjob.result.get("texts", [])
        findings[cid].append(_finding("絵の中の文字・吹き出し", not texts, th["text_score"], f"文字の範囲 {len(texts)}"))
    # 写す範囲・角度（VLM。比べるだけで落とさない）
    if cand_ids and (want_shot or want_angle):
        text, jid = await q.ask_text(unit, f"{unit.id}:a{attempt}:shot_angle", "shot_angle",
                                     q.user_message(build_shot_angle_question(len(cand_ids)), urls), unit.page_id)
        job_ids.append(jid)
        try:
            judged = parse_shot_angle_answer(text, len(cand_ids))
        except BrokenAnswerError as e:
            raise ApplicationError(f"写す範囲・角度の答えの形が崩れた: {e}", type="broken_response",
                                   non_retryable=True) from e
        for cid, j in zip(cand_ids, judged):
            if want_shot:
                findings[cid].append({**_finding("写す範囲", j.shot == want_shot, None,
                                                 f"VLM {j.shot}・ネーム {want_shot}"), "drop": False})
            if want_angle:
                findings[cid].append({**_finding("角度", j.angle == want_angle, None,
                                                 f"VLM {j.angle}・ネーム {want_angle}"), "drop": False})
    out = []
    async with get_sessionmaker()() as session:
        for cid in cand_ids:
            f = findings[cid] + [_finding(v, None, None, "手段が無い。人が確かめる") for v in HUMAN_ONLY_VIEWS]
            cand = await session.get(HarnessCandidate, cid)
            cand.check = {"findings": f}
            cand.check_verdict = verdict_of(f)
            if cand.check_verdict == "drop":
                cand.dropped_reason = "検査で落ちた: " + "、".join(x["name"] for x in f if x["ok"] is False)
            out.append({"candidate_id": cid, "verdict": cand.check_verdict})
        cost = await q.jobs_cost(session, job_ids)
        await session.commit()
    passed = [o for o in out if o["verdict"] != "drop"]
    signature = "check:" + ",".join(sorted({x["name"] for cid in cand_ids for x in findings[cid] if x["ok"] is False}))
    return {"results": out, "passed": len(passed), "cost": cost, "job_ids": job_ids, "failure": signature}


async def evaluate(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    """args: attempt。落ちなかった候補から、評価役に eval_repeats 回選ばせる。"""
    attempt, repeats = args["attempt"], unit.limits["eval_repeats"]
    async with get_sessionmaker()() as session:
        panel = await session.get(Panel, unit.target_id)
        cands = (await session.execute(select(HarnessCandidate).where(
            HarnessCandidate.unit_id == unit.id, HarnessCandidate.attempt == attempt,
            HarnessCandidate.check_verdict.in_(["pass", "flag"])).order_by(HarnessCandidate.k_index))).scalars().all()
        target = panel_description(panel)
        files = {c.id: (await session.get(ImageFile, c.image_id)) for c in cands}
    if not cands:
        return {"picked": None, "why": "選べる候補が無い", "picks": [], "cost": 0, "job_ids": [], "disagree": False}
    tmp = tempfile.mkdtemp(prefix="v3-harness-pick-")
    paths = {}
    for cid, img in files.items():
        p = os.path.join(tmp, f"{cid}.{img.media_type.split('/')[-1]}")
        with open(p, "wb") as fh:
            fh.write(read_image(img.sha256))
        paths[p] = cid
    picks, whys, job_ids = [], [], []
    for r in range(repeats):
        key = f"{unit.id}:a{attempt}:pick{r}"

        async def ask(question: str, images: list[str], key=key) -> str:
            import base64
            urls = []
            for path in images:
                with open(path, "rb") as fh:
                    urls.append("data:image/png;base64," + base64.b64encode(fh.read()).decode())
            text, jid = await q.ask_text(unit, key, "pick", q.user_message(question, urls), unit.page_id)
            job_ids.append(jid)
            return text

        try:
            got = await pick_candidate(ask, list(paths), target, os.path.join(tmp, f"blind{r}"), salt=key)
        except BrokenAnswerError as e:
            raise ApplicationError(f"評価役の答えの形が崩れた: {e}", type="broken_response", non_retryable=True) from e
        picks.append(paths[got.picked] if got.picked else None)
        whys.append(got.why)
    disagree = len(set(picks)) > 1
    picked = picks[0] if not disagree else None
    async with get_sessionmaker()() as session:
        for c in cands:
            row = await session.get(HarnessCandidate, c.id)
            row.evaluation = {"votes": sum(1 for p in picks if p == c.id), "repeats": repeats, "whys": whys}
            row.picked = c.id == picked
        cost = await q.jobs_cost(session, job_ids)
        await session.commit()
    failure = "evaluate:割れた" if disagree else ("evaluate:なし" if picked is None else None)
    return {"picked": picked, "picks": picks, "why": whys, "disagree": disagree, "cost": cost, "job_ids": job_ids,
            "failure": failure}


async def finalize(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    """人の採用。args: by（採用した人）, candidate_id か image_id（人が直した絵）。"""
    actor = Actor(kind="human", id=args["by"])
    async with get_sessionmaker()() as session:
        image_id = args.get("image_id")
        if image_id is None:
            cand = await session.get(HarnessCandidate, args["candidate_id"])
            image_id = cand.image_id
        panel = await session.get(Panel, unit.target_id)
        if panel.image_id == image_id:
            return {"image_id": image_id, "already": True}
        op = AdoptImage(panel_id=unit.target_id, image_id=image_id)
        await submit(session, await q.authz(), actor, unit.work_id, op)
        return {"image_id": image_id}


async def discard_round(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    """取り消した回の候補の絵を「却下」にする（半端な候補を候補の一覧に残さない）。args: attempt, reason, by（取り消し・却下をした人）"""
    async with get_sessionmaker()() as session:
        panel = await session.get(Panel, unit.target_id)
        cands = (await session.execute(select(HarnessCandidate).where(
            HarnessCandidate.unit_id == unit.id, HarnessCandidate.attempt == args["attempt"]))).scalars().all()
        done = []
        # 絵の却下はAIが出せない操作。取り消し・却下をした人の操作として出す
        actor = Actor(kind="human", id=args["by"])
        for c in cands:
            if c.status == "requested":
                c.status = "cancelled"
            c.dropped_reason = c.dropped_reason or args["reason"]
            if c.image_id and c.image_id != (panel.image_id if panel else None):
                img = await session.get(ImageFile, c.image_id)
                if not img.discarded:
                    await submit(session, await q.authz(), actor, unit.work_id,
                                 SetImageDiscarded(image_id=c.image_id, discarded=True))
                    done.append(c.image_id)
        await session.commit()
        return {"discarded": done}
