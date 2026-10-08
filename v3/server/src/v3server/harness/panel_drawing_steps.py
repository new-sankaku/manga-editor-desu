"""作画（S4）の1コマの作業の段（設計 8.1・8.2）。作業の流れ（unit_workflow.py）が段ごとに活動として呼ぶ。

- 文脈：固定の部分（設定資料の人物の生成の言葉・作品の絵の言葉）はプログラムが組み、コマごとに変わる部分（タグ）だけを
  LLM に作らせる（redo_instruction_question）。作り方の道（下絵・正本の背景の切り出し・3Dの背景・1回で描く）と人物の置き場
  （範囲ごとの文か骨格）を panel_drawing_inputs.plan_panel で決め、足りない入力を道の記録に書く
- 生成：k 枚を今の順番待ちに頼む。道ごとに、背景（text_to_image＋奥行きか線画の形の指定）→人物を描き足す（inpaint）か、
  1回で描く（text_to_image）。どの依頼も役目（background・composite・draw）と一緒に候補の made_with に残す（画面の図が
  送り先ごとに分けて出す）
- 検査：大きさ・人数・見切れ・ネームの人物の範囲と検出した人物の重なり（IoU）・顔と吹き出しの重なり（p47）・絵の中の文字・
  同じ人物か（CCIP。「違う」で落とす専用。p43）・手（検出だけ。崩れの判定器は無い）・年齢区分（記録だけ）・写す範囲と角度（VLM）。
  手段の無い観点は「判定できない」として必ず判断待ちに出す（設計 8.2 の最後）
- 直させる：検査で落ちた所が文字か顔だけなら、その範囲だけを囲んで inpaint か指示で直し、直した候補だけを検査し直す
  （回数は作業の上限 max_fix_rounds。上限で落ちたままなら、全部を作り直すことを流れが出来事に書く）
- 評価：落ちなかった候補を総当たりの組にし、左右を入れ替えて2回聞く（pair_comparison。食い違いは引き分け）。
  勝ち＋引き分けの半分で並べ、1位が1枚に決まらなければ選ばない。eval_repeats 回聞いて1位が変われば「割れた」
- 確定：人の採用で、操作の窓口（AdoptImage）を人の操作として通す

閾値は作品の Threshold の表の harness.drawing.* の行を読む。基本の3つ（THRESHOLDS）が無ければ作業は blocked。検査の条件が
揃ったときだけ使う閾値（CONDITIONAL_THRESHOLDS）は、その検査をするコマで無ければ blocked。どれも黙って通さない。
status=unverified（仮）の閾値で外れた候補は落とさず指摘だけ、verified（確定）で外れたら落とす（設計 7.1）。
"""

import base64
import hashlib
import io
import itertools
import os
import tempfile
from types import SimpleNamespace
from typing import Any

from PIL import Image
from sqlalchemy import select
from temporalio.exceptions import ApplicationError

from v3server.canonical_tables.harness_tables import HarnessCandidate, HarnessStageRun, HarnessUnit
from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.service_and_job_tables import Job
from v3server.canonical_tables.text_and_layer_tables import TextItem
from v3server.canonical_tables.threshold_and_finding_tables import Threshold
from v3server.canonical_tables.work_tree_tables import Page, Panel
from v3server.database_engine import get_sessionmaker
from v3server.harness import queue_calls as q
from v3server.harness.panel_drawing_inputs import (
    DrawingSpec,
    box_px,
    control_fields,
    people_mask,
    placement_params,
    plan_panel,
    scene_image,
    size_for_frame,
)
from v3server.harness.upstream_versions import (
    DRAWING_THRESHOLD_PREFIX,
    characters_by_name,
    panel_people_names,
)
from v3server.image_file_storage import read_image, store_image
from v3server.judge_procedures.pair_comparison import ImagePair, compare_pairs
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

__all__ = ["DrawingSpec", "THRESHOLDS", "CONDITIONAL_THRESHOLDS", "HUMAN_ONLY_VIEWS", "size_for_frame"]

# 作画の検査が必ず読む閾値（値の形は {"value": 数}）
THRESHOLDS = {
    "person_score": "人物の検出の score の下限",
    "edge_px": "見切れとみなす、枠が絵の端から何画素以内か",
    "text_score": "絵の中の文字の検出の score の下限",
}
# 検査の条件が揃ったコマでだけ読む閾値
CONDITIONAL_THRESHOLDS = {
    "person_iou_min": "ネームの人物の範囲と検出した人物の重なり（IoU）の下限（ネームに人物の範囲があるコマ）",
    "ccip_threshold": "同じ人物とみなす CCIP の差の上限（設定資料に人物の絵があるコマ）",
    "face_covered_max": "顔が吹き出しに隠れてよい割合の上限（吹き出しを置いたコマ）",
}
# 手段が無く、人の確認に回す観点（設計 8.2）
HUMAN_ONLY_VIEWS = ("背景", "視線", "ぼやけ・線の潰れ", "服・アクセサリー・小物")
# 直させられる検査の名前と、直す所の種類（FixSpec.words の鍵）
FIXABLE = {"絵の中の文字・吹き出し": "text", "同じ人物（CCIP）": "face"}
# 同じ人物の判定をしない小さな人物（高さの割合。p43：小さい人物は差が大きく出た）
CCIP_MIN_H_RATIO = 0.2


async def drawing_thresholds(session, work_id: str) -> dict[str, dict[str, Any]]:
    """{名前: {value, status, source}}。基本の3つが足りなければ blocked。"""
    rows = (await session.execute(select(Threshold).where(
        Threshold.work_id == work_id, Threshold.key.like(DRAWING_THRESHOLD_PREFIX + "%")))).scalars().all()
    got = {t.key[len(DRAWING_THRESHOLD_PREFIX):]: t for t in rows if t.status != "rejected"}
    missing = [k for k in THRESHOLDS if k not in got]
    if missing:
        raise q.blocked("作画の検査の閾値が未設定: " + "、".join(f"{DRAWING_THRESHOLD_PREFIX}{k}（{THRESHOLDS[k]}）"
                                                     for k in missing), missing=[DRAWING_THRESHOLD_PREFIX + k
                                                                                 for k in missing])
    return {k: {"value": float(t.value["value"]), "status": t.status, "source": t.source} for k, t in got.items()}


async def text_boxes_mm(session, panel_id: str) -> list[list[float]]:
    """コマに置いた文字（吹き出し・語り・擬音）の範囲（ページの mm）。仕上げ（S5）で人が置く。置く前は空。"""
    rows = (await session.execute(select(TextItem.box_mm).where(
        TextItem.panel_id == panel_id, TextItem.removed.is_(False), TextItem.box_mm.is_not(None)))).scalars().all()
    return [list(b) for b in rows]


def _require(th: dict[str, Any], keys: list[str]) -> None:
    missing = [k for k in keys if k not in th]
    if missing:
        raise q.blocked("このコマの検査に要る閾値が未設定: " + "、".join(
            f"{DRAWING_THRESHOLD_PREFIX}{k}（{CONDITIONAL_THRESHOLDS[k]}）" for k in missing),
            missing=[DRAWING_THRESHOLD_PREFIX + k for k in missing])


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
    """args: attempt, reject_reason, previous_tags, restart（文脈を捨てて出直す）"""
    spec = DrawingSpec.model_validate(unit.spec["drawing"])
    async with get_sessionmaker()() as session:
        panel = await session.get(Panel, unit.target_id)
        thresholds = await drawing_thresholds(session, unit.work_id)
        for key in ("panel_tags", "detect_person", "detect_text", "detect_hands", "detect_age", "shot_angle", "pair"):
            await q.require_route(session, key)
        width, height = size_for_frame(panel.frame, spec.long_side)
        chars = await characters_by_name(session, unit.work_id)
        fixed, negative, people = [], [spec.negative_words], []
        for name in panel_people_names(panel):
            m = chars.get(name)
            if m is None:
                raise q.blocked(f"設定資料に人物 {name} が無い（採った人物だけを使う）", character=name)
            prompt = (m.generation or {}).get("prompt")
            if not prompt:
                raise q.blocked(f"設定資料の人物 {name} に生成の言葉（generation.prompt）が無い。特徴の言葉は毎回全部入れる"
                                "（試作 p17）ので、人が設定資料に書く", character=name)
            fixed.append(prompt)
            people.append({"name": name, "prompt": prompt, "reference_image_id": (m.image_ids or [None])[0]})
            if (m.generation or {}).get("negative_prompt"):
                negative.append(m.generation["negative_prompt"])
        plan = await plan_panel(session, unit.work_id, panel, spec, people, width, height)
        if plan["placement"] is not None:
            _require(thresholds, ["person_iou_min"])
        if any(p["reference_image_id"] for p in people):
            await q.require_route(session, "detect_identity")
            _require(thresholds, ["ccip_threshold"])
        balloons_mm = await text_boxes_mm(session, panel.id)
        if balloons_mm and people:
            _require(thresholds, ["face_covered_max"])
        if plan["route"] in ("background_crop", "background_3d") or spec.fix is not None:
            await q.require_route(session, "inpaint")
        if spec.fix is not None:
            await q.require_route(session, spec.fix.process)
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
            "job_ids": [job_id], "plan": plan, "balloons_mm": balloons_mm}


def _register(panel: Panel, role: str) -> dict[str, Any]:
    return {"role": role, "page_id": panel.page_id, "panel_id": panel.id}


def _image_request(process: str, params: dict[str, Any], seed: int, set_id: str, panel: Panel, cand_id: str,
                   role: str, inputs: list[dict[str, Any]], protected: bool) -> dict[str, Any]:
    req: dict[str, Any] = {
        "image_process": {"name": process, "params": params, "seed": seed, "candidate_set_id": set_id[:32],
                          "requested_params": params},
        "register": _register(panel, role),
        # 進み具合の鍵は候補の id（画面は候補ごとに段数と途中の絵を出す。背景と描き足しは同じ鍵を順に使う）
        "progress_key": cand_id,
    }
    if inputs:
        req["input_images"] = inputs
    if protected:
        req["protected_mask_input"] = {"node": "protected_mask", "input": "image"}
    return req


def _control_input(png_b64: str | None = None, image_id: str | None = None) -> dict[str, Any]:
    e = {"node": "control", "input": "image", "purpose": "control"}
    if png_b64 is not None:
        e["png_base64"] = png_b64
    else:
        e["image_id"] = image_id
    return e


def _first_requests(spec: DrawingSpec, ctx: dict[str, Any], panel: Panel, cand: HarnessCandidate,
                    set_id: str, source: str | None) -> tuple[str, str, dict[str, Any]]:
    """1つ目の依頼（役目, 処理, 依頼）。道ごとに決める。"""
    plan, text = ctx["plan"], {"prompt": ctx["prompt"], "negative_prompt": ctx["negative_prompt"]}
    w, h = plan["size"]
    if source:
        # 人が直した絵から続ける（人の手の範囲は今の仕組みで貼り戻す）
        params = {**spec.redraw_params, **text}
        return "draw", "image_to_image", _image_request(
            "image_to_image", params, cand.seed, set_id, panel, cand.id, "panel_art",
            [{"node": "source", "input": "image", "image_id": source, "purpose": "source"}], True)
    if plan["route"] == "rough":
        # 下絵が人物の置き場も決めるので、骨格は渡さない（形の指定は1つ）。範囲ごとの文は文の側なので渡せる
        place = placement_params(spec, plan, w, h)[0] if plan["placement"] == "region" else {}
        params = {**spec.base_params, **text, "width": w, "height": h, **control_fields(spec, "lineart", True), **place}
        return "draw", "text_to_image", _image_request("text_to_image", params, cand.seed, set_id, panel, cand.id,
                                                       "panel_art", [_control_input(image_id=plan["rough_image_id"])],
                                                       False)
    if plan["route"] == "background_3d":
        bg = spec.background
        loc = plan["background"]
        params = {**bg.params, "prompt": ", ".join(x for x in (spec.quality_words, spec.style_words, loc["prompt"])
                                                   if x.strip()),
                  "negative_prompt": ctx["negative_prompt"], "width": w, "height": h,
                  **control_fields(spec, bg.control, bg.control == "lineart")}
        img = scene_image(loc["scene3d"], plan["view"], w, h, bg)
        role = "background" if plan["people"] else "panel_art"
        return "background", "text_to_image", _image_request("text_to_image", params, cand.seed, set_id, panel,
                                                             cand.id, role, [_control_input(png_b64=img)], False)
    if plan["route"] == "background_crop":
        crop = plan["background"]
        src = {"node": "source", "input": "image", "image_id": crop["image_id"], "purpose": "source",
               "crop_px": crop["crop_px"]}
        if not plan["people"]:
            params = {**spec.redraw_params, **text}
            return "draw", "image_to_image", _image_request("image_to_image", params, cand.seed, set_id, panel,
                                                            cand.id, "panel_art", [src], True)
        return ("composite", "inpaint", _composite_request(spec, ctx, panel, cand, set_id, src, w, h))
    # single：背景と人物を1回で描く。人物の置き場は範囲ごとの文か骨格
    place, pose = placement_params(spec, plan, w, h)
    params = {**spec.base_params, **text, "width": w, "height": h, **place}
    return "draw", "text_to_image", _image_request("text_to_image", params, cand.seed, set_id, panel, cand.id,
                                                   "panel_art", [_control_input(png_b64=pose)] if pose else [], False)


def _composite_request(spec: DrawingSpec, ctx: dict[str, Any], panel: Panel, cand: HarnessCandidate, set_id: str,
                       source: dict[str, Any], w: int, h: int) -> dict[str, Any]:
    """背景の上に、人物の範囲だけを囲んで人物を描く（inpaint）。"""
    plan = ctx["plan"]
    place, pose = placement_params(spec, plan, w, h)
    params = {**spec.background.composite_params, "prompt": ctx["prompt"], "negative_prompt": ctx["negative_prompt"],
              **place}
    inputs = [source, {"node": "mask", "input": "image", "purpose": "mask", "region_px": people_mask(plan, w, h)}]
    if pose:
        inputs.append(_control_input(png_b64=pose))
    return _image_request("inpaint", params, cand.seed, set_id, panel, cand.id, "panel_art", inputs, True)


async def _job_row(session, job_id: str) -> dict[str, Any]:
    j = await session.get(Job, job_id)
    return {"job_id": j.id, "process": j.process, "service_id": j.service_id, "status": j.status}


async def generate(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    """args: attempt, context（文脈の段の答え）, seeds, edit_image_id（人が直した絵から続けるとき）"""
    spec = DrawingSpec.model_validate(unit.spec["drawing"])
    ctx, attempt, k = args["context"], args["attempt"], unit.limits["candidates_per_attempt"]
    source = args.get("edit_image_id")
    if source and spec.redraw_params is None:
        raise q.blocked("人が直した絵から続けるには、作業の決めごとに redraw_params（image_to_image の引数）が要る")
    plan = ctx["plan"]
    set_id = f"{unit.id}a{attempt}"
    cand_ids, first_jobs = [], []
    async with get_sessionmaker()() as session:
        panel = await session.get(Panel, unit.target_id)
        for i in range(k):
            hkey = f"{unit.id}:a{attempt}:gen{i}"
            cand = (await session.execute(select(HarnessCandidate).where(
                HarnessCandidate.harness_key == hkey))).scalar_one_or_none()
            if cand is None:
                cand = HarnessCandidate(unit_id=unit.id, attempt=attempt, k_index=i, harness_key=hkey,
                                        seed=args["seeds"][i], prompt=ctx["prompt"], status="requested", picked=False,
                                        fix_round=0)
                session.add(cand)
                await session.commit()
            elif cand.status == "cancelled":
                # 人が今すぐ止めた段を再開した。同じ候補で頼み直す（ensure_job が新しい依頼を作る）
                cand.status, cand.dropped_reason = "requested", None
            role, process, request = _first_requests(spec, ctx, panel, cand, set_id, source)
            await q.require_route(session, process)
            job = await q.ensure_job(session, unit, hkey, process, request, panel.page_id)
            cand.job_id = job.id
            cand.made_with = {"route": "edit" if source else plan["route"], "placement": plan["placement"],
                              "used": plan["used"], "missing": plan["missing"],
                              "jobs": [{"role": role, "job_id": job.id, "process": process}], "intermediate": []}
            await session.commit()
            cand_ids.append(cand.id)
            first_jobs.append((role, job.id))
    jobs = await q.wait_jobs(unit.id, [j for _, j in first_jobs])
    all_job_ids = [j for _, j in first_jobs]
    # 背景を先に作った候補は、人物を描き足す依頼を続けて出す
    second: dict[str, str] = {}
    async with get_sessionmaker()() as session:
        panel = await session.get(Panel, unit.target_id)
        for cid, (role, _), job in zip(cand_ids, first_jobs, jobs, strict=True):
            if role != "background" or not plan["people"] or job.status != "done":
                continue
            cand = await session.get(HarnessCandidate, cid)
            bg_image = job.result["registered"][0]["image_id"]
            w, h = plan["size"]
            src = {"node": "source", "input": "image", "image_id": bg_image, "purpose": "source"}
            request = _composite_request(spec, ctx, panel, cand, set_id, src, w, h)
            await q.require_route(session, "inpaint")
            j2 = await q.ensure_job(session, unit, f"{unit.id}:a{attempt}:comp{cand.k_index}", "inpaint", request,
                                    panel.page_id)
            cand.made_with = {**cand.made_with, "jobs": cand.made_with["jobs"] + [
                {"role": "composite", "job_id": j2.id, "process": "inpaint"}], "intermediate": [bg_image]}
            cand.job_id = j2.id
            second[cid] = j2.id
            await session.commit()
    if second:
        done2 = await q.wait_jobs(unit.id, list(second.values()))
        by_id = {j.id: j for j in done2}
        jobs = [by_id[second[cid]] if cid in second else j for cid, j in zip(cand_ids, jobs, strict=True)]
        all_job_ids += list(second.values())
    out = []
    async with get_sessionmaker()() as session:
        for cid, job in zip(cand_ids, jobs, strict=True):
            cand = await session.get(HarnessCandidate, cid)
            if job.status == "done" and job.result.get("registered"):
                cand.image_id, cand.status = job.result["registered"][0]["image_id"], "generated"
            else:
                cand.status = "failed" if job.status == "stopped" else "cancelled"
                cand.dropped_reason = f"生成が止まった（{job.failure_kind}）: {job.failure_detail}"
            cand.made_with = {**cand.made_with, "jobs": [{**x, **(await _job_row(session, x["job_id"]))}
                                                         for x in cand.made_with["jobs"]]}
            out.append({"candidate_id": cid, "image_id": cand.image_id, "status": cand.status,
                        "failure_kind": job.failure_kind})
        cost = await q.jobs_cost(session, all_job_ids)
        await session.commit()
    refused = [o for o in out if o["failure_kind"] == "refused"]
    if refused and len(refused) == len(out):
        raise ApplicationError(f"生成が全部断られた: {jobs[0].failure_detail}", type="refused", non_retryable=True)
    if not any(o["image_id"] for o in out):
        raise ApplicationError("生成が全部止まった", {"kinds": [o["failure_kind"] for o in out]},
                               type="generation_failed", non_retryable=True)
    return {"candidates": out, "cost": cost, "job_ids": all_job_ids, "route": "edit" if source else plan["route"],
            "placement": plan["placement"], "used": plan["used"], "missing": plan["missing"]}


# ---------------------------------------------------------------- 検査


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


def iou(a: list[float], b: list[float]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def match_people(want: list[list[float]], got: list[list[float]]) -> list[tuple[int, int | None, float]]:
    """ネームの人物の範囲ごとに、いちばん重なる検出の人物（一度使った検出は使わない。重なりの大きい組から決める）。"""
    pairs = sorted(((iou(w, g), i, j) for i, w in enumerate(want) for j, g in enumerate(got)), reverse=True)
    used_w, used_g, out = set(), set(), {}
    for v, i, j in pairs:
        if i in used_w or j in used_g or v <= 0:
            continue
        used_w.add(i)
        used_g.add(j)
        out[i] = (i, j, v)
    return [out.get(i, (i, None, 0.0)) for i in range(len(want))]


def covered_ratio(face: list[float], balloons: list[list[float]]) -> float:
    """顔の枠のうち、吹き出しの枠に隠れる割合（吹き出しどうしの重なりは数え過ぎないよう 1 で切る）。"""
    area = (face[2] - face[0]) * (face[3] - face[1])
    if area <= 0:
        return 0.0
    s = 0.0
    for b in balloons:
        ix = max(0.0, min(face[2], b[2]) - max(face[0], b[0]))
        iy = max(0.0, min(face[3], b[3]) - max(face[1], b[1]))
        s += ix * iy
    return min(1.0, s / area)


def _xyxy(d: dict[str, Any]) -> list[float]:
    return [float(d["x0"]), float(d["y0"]), float(d["x1"]), float(d["y1"])]


def _crop_png(data: bytes, box: list[float]) -> bytes:
    with Image.open(io.BytesIO(data)) as im:
        buf = io.BytesIO()
        im.crop(tuple(int(round(v)) for v in box)).convert("RGB").save(buf, format="PNG")
        return buf.getvalue()


async def _detect(unit: HarnessUnit, key: str, step: str, endpoint: str, images: dict[str, str],
                  form: dict[str, Any]) -> tuple[Job, str]:
    async with get_sessionmaker()() as session:
        process = await q.require_route(session, step)
        job = await q.ensure_job(session, unit, key, process, {"endpoint": endpoint, "images": images, "form": form},
                                 unit.page_id)
        return job, job.id


async def _check_one(unit: HarnessUnit, cand: HarnessCandidate, img: ImageFile, panel: Panel, ctx: dict[str, Any],
                     refs: dict[str, ImageFile], skip_size: bool) -> tuple[list[dict[str, Any]], list[str]]:
    th, plan = ctx["thresholds"], ctx["plan"]
    findings: list[dict[str, Any]] = []
    job_ids: list[str] = []
    W, H = img.width, img.height
    if not skip_size:
        want = tuple(plan["size"])
        findings.append(_finding("大きさ", (W, H) == want, None, f"{W}x{H}（頼んだ {want[0]}x{want[1]}）"))
    form_p = {"edge_px": int(th["edge_px"]["value"]), "score_threshold": th["person_score"]["value"]}
    pj, _ = await _detect(unit, f"{unit.id}:c{cand.id}:detect_person", "detect_person", "/person_face_head",
                          {"image": img.sha256}, form_p)
    tj, _ = await _detect(unit, f"{unit.id}:c{cand.id}:detect_text", "detect_text", "/text_regions", {"image": img.sha256},
                          {"score_threshold": th["text_score"]["value"]})
    hj, _ = await _detect(unit, f"{unit.id}:c{cand.id}:detect_hands", "detect_hands", "/hands", {"image": img.sha256}, {})
    aj, _ = await _detect(unit, f"{unit.id}:c{cand.id}:detect_age", "detect_age", "/age_rating", {"image": img.sha256}, {})
    ids = [pj.id, tj.id, hj.id, aj.id]
    pjob, tjob, hjob, ajob = await q.wait_jobs(unit.id, ids)
    job_ids += ids
    for j in (pjob, tjob, hjob, ajob):
        if j.status != "done":
            raise q.job_failure(j)
    persons = pjob.result.get("persons", [])
    faces = pjob.result.get("faces", []) + pjob.result.get("heads", [])
    want_people = len(plan["people"])
    findings.append(_finding("人数", len(persons) == want_people, th["person_score"],
                             f"検出 {len(persons)} 人・ネーム {want_people} 人"))
    touching = [p["touch"] for p in persons if p.get("touch")]
    findings.append({**_finding("見切れ", not touching, th["edge_px"],
                                f"端に接した人物 {len(touching)}（{','.join(touching)}）"), "drop": False})
    # ネームの人物の範囲と検出の重なり（IoU）
    got_boxes = [_xyxy(p) for p in persons]
    matches: list[tuple[int, int | None, float]] = []
    if plan["placement"] is not None:
        want_boxes = [box_px(f["box"], W, H) for f in plan["people"]]
        matches = match_people(want_boxes, got_boxes)
        lo = th["person_iou_min"]["value"]
        worst = min((v for _, _, v in matches), default=0.0)
        findings.append(_finding("人物の位置（IoU）", worst >= lo, th["person_iou_min"],
                                 "、".join(f"{plan['people'][i]['name']} {v:.2f}" for i, _, v in matches)
                                 + f"（下限 {lo}）"))
    else:
        findings.append(_finding("人物の位置（IoU）", None, None,
                                 "ネームに人物の範囲が無いので比べない" if plan["people"] else "人物がいない"))
    # 顔と吹き出しの重なり（p47）
    balloons_mm = ctx["balloons_mm"]
    if balloons_mm and plan["people"]:
        fx0, fy0, fx1, fy1 = frame_bbox(panel.frame)
        bpx = [[(b[0] - fx0) / (fx1 - fx0) * W, (b[1] - fy0) / (fy1 - fy0) * H, (b[2] - fx0) / (fx1 - fx0) * W,
                (b[3] - fy0) / (fy1 - fy0) * H] for b in balloons_mm]
        worst = max((covered_ratio(_xyxy(f), bpx) for f in faces), default=0.0)
        hi = th["face_covered_max"]["value"]
        findings.append(_finding("顔と吹き出しの重なり", worst <= hi, th["face_covered_max"],
                                 f"いちばん隠れた顔 {worst:.0%}（上限 {hi:.0%}）。顔の検出 {len(faces)}"))
    else:
        findings.append(_finding("顔と吹き出しの重なり", None, None,
                                 "吹き出しを置いていない（仕上げ S5 で置いた後に検査する）"))
    texts = tjob.result.get("texts", [])
    findings.append({**_finding("絵の中の文字・吹き出し", not texts, th["text_score"], f"文字の範囲 {len(texts)}"),
                     "fix": {"kind": "text", "boxes_px": [_xyxy(t) for t in texts]} if texts else None})
    hands = hjob.result.get("hands", [])
    findings.append(_finding("手", None, None, f"手の検出 {len(hands)}。崩れの判定器は無いので人が見る"))
    rating = ajob.result.get("rating") or {}
    top = max(rating.items(), key=lambda kv: kv[1])[0] if rating else None
    findings.append(_finding("年齢区分", None, None, f"いちばん高い区分 {top}（記録だけ。判定に使わない）"))
    # 同じ人物か（CCIP。「違う」で落とす専用。同じ=true は同じ人物の証拠にならない）
    data = None
    for i, f in enumerate(plan["people"]):
        ref = refs.get(f["name"])
        if ref is None:
            findings.append(_finding("同じ人物（CCIP）", None, None, f"設定資料の {f['name']} に絵が無いので比べない"))
            continue
        if matches:
            j = matches[i][1]
        else:
            j = 0 if len(plan["people"]) == 1 and len(persons) == 1 else None
        if j is None:
            findings.append(_finding("同じ人物（CCIP）", None, None, f"{f['name']} に当たる検出の人物が決められない"))
            continue
        if persons[j].get("h_ratio", 1) < CCIP_MIN_H_RATIO:
            findings.append(_finding("同じ人物（CCIP）", None, None,
                                     f"{f['name']} は小さい（高さ {persons[j].get('h_ratio')}。p43 で差が大きく出た）"))
            continue
        data = data or read_image(img.sha256)
        crop = store_image(_crop_png(data, got_boxes[j]))
        cj, _ = await _detect(unit, f"{unit.id}:c{cand.id}:identity:{i}", "detect_identity", "/identity_ccip",
                              {"image_a": crop.sha256, "image_b": ref.sha256},
                              {"threshold": th["ccip_threshold"]["value"]})
        (cjob,) = await q.wait_jobs(unit.id, [cj.id])
        job_ids.append(cj.id)
        if cjob.status != "done":
            raise q.job_failure(cjob)
        same = bool(cjob.result.get("same"))
        head = next((_xyxy(x) for x in faces if _inside(_xyxy(x), got_boxes[j])), None)
        findings.append({**_finding("同じ人物（CCIP）", True if same else False, th["ccip_threshold"],
                                    f"{f['name']} 差 {cjob.result.get('difference')}（閾値 {cjob.result.get('threshold')}）"
                                    + ("" if same else "。違う人物と出た")),
                         "fix": None if same or head is None else {"kind": "face", "boxes_px": [head],
                                                                   "character": f["name"]}})
    return findings, job_ids


def _inside(inner: list[float], outer: list[float]) -> bool:
    cx, cy = (inner[0] + inner[2]) / 2, (inner[1] + inner[3]) / 2
    return outer[0] <= cx <= outer[2] and outer[1] <= cy <= outer[3]


def fix_targets(findings: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """落ちた理由が全部「直せる所（文字・顔）」なら、直す所の一覧。1つでも直せない理由で落ちていれば None。"""
    failed = [f for f in findings if f["ok"] is False and f["threshold_status"] in (None, "verified")
              and f.get("drop", True)]
    if not failed or any(f["name"] not in FIXABLE or not f.get("fix") for f in failed):
        return None
    return [f["fix"] for f in failed]


async def check(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    """args: attempt, context, skip_size。この回の、まだ検査していない候補だけを検査する（直した候補の検査し直しも同じ）。
    返す数（passed・fixable）はこの回の候補の全部で数える。"""
    ctx, attempt = args["context"], args["attempt"]
    spec = DrawingSpec.model_validate(unit.spec["drawing"])
    async with get_sessionmaker()() as session:
        panel = await session.get(Panel, unit.target_id)
        cands = (await session.execute(select(HarnessCandidate).where(
            HarnessCandidate.unit_id == unit.id, HarnessCandidate.attempt == attempt,
            HarnessCandidate.image_id.is_not(None), HarnessCandidate.check_verdict.is_(None))
            .order_by(HarnessCandidate.fix_round, HarnessCandidate.k_index))).scalars().all()
        imgs = {c.id: await session.get(ImageFile, c.image_id) for c in cands}
        refs = {}
        for f in ctx["plan"]["people"]:
            if f.get("reference_image_id"):
                refs[f["name"]] = await session.get(ImageFile, f["reference_image_id"])
        want_shot, want_angle = panel.content.get("shot"), panel.content.get("angle")
        urls = [await q.image_data_url(session, c.image_id) for c in cands]
    job_ids: list[str] = []
    findings: dict[str, list[dict[str, Any]]] = {}
    for c in cands:
        findings[c.id], jids = await _check_one(unit, c, imgs[c.id], panel, ctx, refs, bool(args.get("skip_size")))
        job_ids += jids
    # 写す範囲・角度（VLM。比べるだけで落とさない）
    if cands and (want_shot or want_angle):
        key = f"{unit.id}:a{attempt}:shot_angle:" + ",".join(c.id[:6] for c in cands)
        text, jid = await q.ask_text(unit, key, "shot_angle",
                                     q.user_message(build_shot_angle_question(len(cands)), urls), unit.page_id)
        job_ids.append(jid)
        try:
            judged = parse_shot_angle_answer(text, len(cands))
        except BrokenAnswerError as e:
            raise ApplicationError(f"写す範囲・角度の答えの形が崩れた: {e}", type="broken_response",
                                   non_retryable=True) from e
        for c, j in zip(cands, judged, strict=True):
            if want_shot:
                findings[c.id].append({**_finding("写す範囲", j.shot == want_shot, None,
                                                  f"VLM {j.shot}・ネーム {want_shot}"), "drop": False})
            if want_angle:
                findings[c.id].append({**_finding("角度", j.angle == want_angle, None,
                                                  f"VLM {j.angle}・ネーム {want_angle}"), "drop": False})
    results = []
    async with get_sessionmaker()() as session:
        for c in cands:
            f = findings[c.id] + [_finding(v, None, None, "手段が無い。人が確かめる") for v in HUMAN_ONLY_VIEWS]
            cand = await session.get(HarnessCandidate, c.id)
            cand.check = {"findings": f}
            cand.check_verdict = verdict_of(f)
            if cand.check_verdict == "drop":
                cand.dropped_reason = "検査で落ちた: " + "、".join(x["name"] for x in f if x["ok"] is False)
            results.append({"candidate_id": c.id, "verdict": cand.check_verdict, "fix_round": c.fix_round,
                            "findings": [{"name": x["name"], "ok": x["ok"], "threshold_status": x["threshold_status"]}
                                         for x in f]})
        cost = await q.jobs_cost(session, job_ids)
        await session.commit()
        alive = (await session.execute(select(HarnessCandidate).where(
            HarnessCandidate.unit_id == unit.id, HarnessCandidate.attempt == attempt,
            HarnessCandidate.check_verdict.is_not(None)))).scalars().all()
    # 直した候補がある元は数えない（直した方を数える）
    superseded = {c.fixed_from for c in alive if c.fixed_from}
    current = [c for c in alive if c.id not in superseded]
    passed = [c for c in current if c.check_verdict != "drop"]
    fixable, why_not = [], None
    for c in current:
        if c.check_verdict != "drop":
            continue
        targets = fix_targets(c.check["findings"])
        if targets is None:
            continue
        if spec.fix is None:
            why_not = "作業の決めごとに fix（直させる段の引数）が無い"
            continue
        fixable.append(c.id)
    failed_names = sorted({x["name"] for c in current if c.check_verdict == "drop" for x in c.check["findings"]
                           if x["ok"] is False})
    return {"results": results, "passed": len(passed), "cost": cost, "job_ids": job_ids,
            "failure": "check:" + ",".join(failed_names), "fixable": fixable, "fix_unavailable": why_not}


# ---------------------------------------------------------------- 直させる


def _grow(box: list[float], px: int, w: int, h: int) -> list[list[int]]:
    x0, y0 = max(0, int(box[0]) - px), max(0, int(box[1]) - px)
    x1, y1 = min(w, int(box[2]) + px), min(h, int(box[3]) + px)
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


async def fix(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    """args: attempt, context, round, candidate_ids（直す候補）。落ちた所だけを囲んで直した候補を足す。"""
    spec = DrawingSpec.model_validate(unit.spec["drawing"])
    fx = spec.fix
    ctx, attempt, rnd = args["context"], args["attempt"], args["round"]
    made, job_ids = [], []
    async with get_sessionmaker()() as session:
        panel = await session.get(Panel, unit.target_id)
        process = await q.require_route(session, fx.process)
        for cid in args["candidate_ids"]:
            src = await session.get(HarnessCandidate, cid)
            img = await session.get(ImageFile, src.image_id)
            targets = fix_targets(src.check["findings"])
            kinds = sorted({t["kind"] for t in targets})
            polys = [_grow(b, fx.grow_px, img.width, img.height) for t in targets for b in t["boxes_px"]]
            hkey = f"{unit.id}:a{attempt}:fix{rnd}:{src.k_index}"
            cand = (await session.execute(select(HarnessCandidate).where(
                HarnessCandidate.harness_key == hkey))).scalar_one_or_none()
            if cand is None:
                cand = HarnessCandidate(unit_id=unit.id, attempt=attempt, k_index=src.k_index, harness_key=hkey,
                                        seed=src.seed, prompt=src.prompt, status="requested", picked=False,
                                        fixed_from=src.id, fix_round=rnd)
                session.add(cand)
                await session.flush()
            if fx.process == "inpaint":
                params = {**fx.params, "prompt": ", ".join([ctx["prompt"], *(fx.words[k] for k in kinds)]),
                          "negative_prompt": ctx["negative_prompt"]}
            else:
                params = {**fx.params, "instruction": "\n".join(fx.words[k] for k in kinds)}
            inputs = [{"node": "source", "input": "image", "image_id": src.image_id, "purpose": "source"},
                      {"node": "mask", "input": "image", "purpose": "mask", "region_px": polys}]
            request = _image_request(fx.process, params, src.seed, f"{unit.id}f{rnd}", panel, cand.id, "panel_art",
                                     inputs, True)
            job = await q.ensure_job(session, unit, hkey, process, request, panel.page_id)
            cand.job_id = job.id
            cand.made_with = {**(src.made_with or {}), "fix": {"kinds": kinds, "regions_px": polys, "from": src.id},
                              "jobs": [{"role": "fix", "job_id": job.id, "process": fx.process}]}
            src.dropped_reason = f"検査で落ちた所を直させた（{fx.process}・{'、'.join(kinds)}）。直した候補を使う"
            await session.commit()
            made.append(cand.id)
            job_ids.append(job.id)
    jobs = await q.wait_jobs(unit.id, job_ids)
    out = []
    async with get_sessionmaker()() as session:
        for cid, job in zip(made, jobs, strict=True):
            cand = await session.get(HarnessCandidate, cid)
            if job.status == "done" and job.result.get("registered"):
                cand.image_id, cand.status = job.result["registered"][0]["image_id"], "generated"
            else:
                cand.status, cand.check_verdict = "failed", "drop"
                cand.dropped_reason = f"直す依頼が止まった（{job.failure_kind}）: {job.failure_detail}"
                cand.check = {"findings": []}
            cand.made_with = {**cand.made_with, "jobs": [{**x, **(await _job_row(session, x["job_id"]))}
                                                         for x in cand.made_with["jobs"]]}
            out.append({"candidate_id": cid, "from": cand.fixed_from, "status": cand.status,
                        "kinds": cand.made_with["fix"]["kinds"]})
        cost = await q.jobs_cost(session, job_ids)
        await session.commit()
    return {"fixed": out, "round": rnd, "process": fx.process, "cost": cost, "job_ids": job_ids}


# ---------------------------------------------------------------- 評価


async def evaluate(unit: HarnessUnit, args: dict[str, Any]) -> dict[str, Any]:
    """args: attempt。落ちなかった候補を総当たりで2枚ずつ比べる（左右を入れ替えて2回。食い違いは引き分け）。"""
    attempt, repeats = args["attempt"], unit.limits["eval_repeats"]
    async with get_sessionmaker()() as session:
        panel = await session.get(Panel, unit.target_id)
        rows = (await session.execute(select(HarnessCandidate).where(
            HarnessCandidate.unit_id == unit.id, HarnessCandidate.attempt == attempt,
            HarnessCandidate.check_verdict.in_(["pass", "flag"])).order_by(
            HarnessCandidate.k_index, HarnessCandidate.fix_round))).scalars().all()
        superseded = {c.fixed_from for c in rows if c.fixed_from}
        cands = [c for c in rows if c.id not in superseded]
        target = panel_description(panel).replace("\n", "／")
        files = {c.id: (await session.get(ImageFile, c.image_id)) for c in cands}
    if not cands:
        return {"picked": None, "why": "選べる候補が無い", "rounds": [], "cost": 0, "job_ids": [], "disagree": False,
                "failure": "evaluate:なし"}
    if len(cands) == 1:
        async with get_sessionmaker()() as session:
            row = await session.get(HarnessCandidate, cands[0].id)
            row.evaluation, row.picked = {"score": None, "why": "比べる相手が無い（通った候補が1枚）"}, True
            await session.commit()
        return {"picked": cands[0].id, "why": "通った候補が1枚なので比べずに選んだ", "rounds": [], "cost": 0,
                "job_ids": [], "disagree": False, "failure": None}
    tmp = tempfile.mkdtemp(prefix="v3-harness-pair-")
    path_of, cid_of = {}, {}
    for cid, img in files.items():
        p = os.path.join(tmp, f"{cid}.{img.media_type.split('/')[-1]}")
        with open(p, "wb") as fh:
            fh.write(read_image(img.sha256))
        path_of[cid], cid_of[p] = p, cid
    pairs = [ImagePair(path_of[a.id], path_of[b.id]) for a, b in itertools.combinations(cands, 2)]
    criterion = f"狙い「{target}」に、AとBのどちらの絵が合っているかを答えてください。"
    job_ids: list[str] = []
    rounds, tops, scores_by_repeat = [], [], []
    for r in range(repeats):
        async def ask(question: str, images: list[str]) -> str:
            urls = []
            for path in images:
                with open(path, "rb") as fh:
                    urls.append("data:image/png;base64," + base64.b64encode(fh.read()).decode())
            key = f"{unit.id}:a{attempt}:pair:" + hashlib.sha256(question.encode()).hexdigest()[:16]
            text, jid = await q.ask_text(unit, key, "pair", q.user_message(question, urls), unit.page_id)
            job_ids.append(jid)
            return text

        try:
            outcomes = await compare_pairs(ask, pairs, criterion, os.path.join(tmp, f"blind{r}"),
                                           salt=f"{unit.id}:a{attempt}:r{r}")
        except BrokenAnswerError as e:
            raise ApplicationError(f"評価役の答えの形が崩れた: {e}", type="broken_response", non_retryable=True) from e
        score = {c.id: {"wins": 0, "ties": 0, "losses": 0} for c in cands}
        for o in outcomes:
            a, b = cid_of[o.pair.left], cid_of[o.pair.right]
            rounds.append({"repeat": r, "a": a, "b": b, "first": o.first, "second": o.second, "verdict": o.verdict})
            if o.verdict == "tie":
                score[a]["ties"] += 1
                score[b]["ties"] += 1
            else:
                win, lose = (a, b) if o.verdict == "left" else (b, a)
                score[win]["wins"] += 1
                score[lose]["losses"] += 1
        total = {cid: s["wins"] + s["ties"] / 2 for cid, s in score.items()}
        best = max(total.values())
        top = [cid for cid, v in total.items() if v == best]
        tops.append(top[0] if len(top) == 1 else None)
        scores_by_repeat.append({cid: {**s, "score": total[cid]} for cid, s in score.items()})
    disagree = len(set(tops)) > 1
    picked = tops[0] if not disagree else None
    async with get_sessionmaker()() as session:
        for c in cands:
            row = await session.get(HarnessCandidate, c.id)
            row.evaluation = {"repeats": [s[c.id] for s in scores_by_repeat], "top_count": tops.count(c.id)}
            row.picked = c.id == picked
        cost = await q.jobs_cost(session, job_ids)
        await session.commit()
    failure = "evaluate:割れた" if disagree else ("evaluate:同点" if picked is None else None)
    why = ("くり返すと1位が変わった" if disagree else "1位が1枚に決まらない（同点）" if picked is None
           else "勝ち＋引き分けの半分がいちばん多い")
    return {"picked": picked, "tops": tops, "why": why, "rounds": rounds, "scores": scores_by_repeat,
            "disagree": disagree, "cost": cost, "job_ids": job_ids, "failure": failure}


# ---------------------------------------------------------------- 確定・却下


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
    """取り消した回の候補の絵（背景など途中の絵も）を「却下」にする。args: attempt, reason, by（取り消し・却下をした人）"""
    async with get_sessionmaker()() as session:
        panel = await session.get(Panel, unit.target_id)
        cands = (await session.execute(select(HarnessCandidate).where(
            HarnessCandidate.unit_id == unit.id, HarnessCandidate.attempt == args["attempt"]))).scalars().all()
        done = []
        # 絵の却下はAIが出せない操作。取り消し・却下をした人の操作として出す
        actor = Actor(kind="human", id=args["by"])
        keep = panel.image_id if panel else None
        for c in cands:
            if c.status == "requested":
                c.status = "cancelled"
            c.dropped_reason = c.dropped_reason or args["reason"]
            for image_id in [c.image_id, *((c.made_with or {}).get("intermediate") or [])]:
                if not image_id or image_id == keep or image_id in done:
                    continue
                img = await session.get(ImageFile, image_id)
                if not img.discarded:
                    await submit(session, await q.authz(), actor, unit.work_id,
                                 SetImageDiscarded(image_id=image_id, discarded=True))
                    done.append(image_id)
        await session.commit()
        return {"discarded": done}


# ---------------------------------------------------------------- 工程の検査（コマをまたぐ一致）


async def drift_check(session, run: HarnessStageRun) -> dict[str, Any]:
    """採った絵の人物が、設定資料の絵と「違う」と出たコマ（一致が崩れたコマ）。そのコマの作業だけを作り直せるよう返す。
    比べるのは、設定資料に絵のある人物が1人だけ写るコマ（人物と検出の対応が決まる所）。ほかは比べないと書く。"""
    asker = SimpleNamespace(id=None, work_id=run.work_id, requested_by=run.requested_by)
    units = (await session.execute(select(HarnessUnit).where(
        HarnessUnit.stage_run_id == run.id, HarnessUnit.status == "done"))).scalars().all()
    chars = await characters_by_name(session, run.work_id)
    th = await drawing_thresholds(session, run.work_id)
    drifted, compared, skipped = [], [], []
    for u in units:
        panel = await session.get(Panel, u.target_id)
        names = panel_people_names(panel)
        if not panel.image_id:
            continue
        refs = [chars[n].image_ids[0] for n in names if n in chars and chars[n].image_ids]
        if len(names) != 1 or len(refs) != 1:
            skipped.append({"unit_id": u.id, "why": "設定資料に絵のある人物が1人だけ写るコマでない"})
            continue
        _require(th, ["ccip_threshold"])
        img = await session.get(ImageFile, panel.image_id)
        ref = await session.get(ImageFile, refs[0])
        await q.require_route(session, "detect_person")
        await q.require_route(session, "detect_identity")
        pj = await q.ensure_job(session, asker, f"{run.id}:drift:{u.id}:{img.id}:person",
                                q.HARNESS_PROCESSES["detect_person"],
                                {"endpoint": "/person_face_head", "images": {"image": img.sha256},
                                 "form": {"edge_px": int(th["edge_px"]["value"]),
                                          "score_threshold": th["person_score"]["value"]}}, panel.page_id)
        await session.commit()
        (pjob,) = await q.wait_jobs(None, [pj.id])
        if pjob.status != "done":
            raise q.job_failure(pjob)
        persons = pjob.result.get("persons", [])
        if len(persons) != 1 or persons[0].get("h_ratio", 1) < CCIP_MIN_H_RATIO:
            skipped.append({"unit_id": u.id, "why": f"検出の人物 {len(persons)} 人（1人で高さ2割以上のときだけ比べる）"})
            continue
        crop = store_image(_crop_png(read_image(img.sha256), _xyxy(persons[0])))
        cj = await q.ensure_job(session, asker, f"{run.id}:drift:{u.id}:{img.id}:ccip",
                                q.HARNESS_PROCESSES["detect_identity"],
                                {"endpoint": "/identity_ccip", "images": {"image_a": crop.sha256, "image_b": ref.sha256},
                                 "form": {"threshold": th["ccip_threshold"]["value"]}}, panel.page_id)
        await session.commit()
        (cjob,) = await q.wait_jobs(None, [cj.id])
        if cjob.status != "done":
            raise q.job_failure(cjob)
        row = {"unit_id": u.id, "panel_id": panel.id, "character": names[0],
               "difference": cjob.result.get("difference"), "same": bool(cjob.result.get("same"))}
        compared.append(row)
        if not row["same"]:
            drifted.append(u.id)
    return {"drifted_units": drifted, "drift_compared": compared, "drift_skipped": skipped}


async def page_summary(session, run: HarnessStageRun) -> list[dict[str, Any]]:
    pages = (await session.execute(select(Page).where(Page.episode_id == run.episode_id, Page.removed.is_(False))
                                   .order_by(Page.number))).scalars().all()
    out = []
    for p in pages:
        panels = (await session.execute(select(Panel).where(Panel.page_id == p.id, Panel.removed.is_(False))
                                        .order_by(Panel.order))).scalars().all()
        out.append({"page_id": p.id, "number": p.number, "panels": len(panels),
                    "with_image": sum(1 for x in panels if x.image_id),
                    "missing": [x.id for x in panels if not x.image_id]})
    return out
