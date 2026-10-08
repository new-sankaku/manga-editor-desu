"""P60 の活動（Temporal の activity）。AI と ComfyUI と検出器の呼び出し1回が1つの活動。
絵は置き場（STORE）のファイル名だけを渡す（Temporal の履歴に絵を載せない）。

記録のファイル（数えるため。どれも1行1件の追記）
- prompt_posts.jsonl：ComfyUI の /prompt に実際に送った回
- registrations.jsonl：置き場への登録・登録の取り下げ・既にあったので登録しなかった回
- claude_calls.jsonl：Claude の CLI を呼んだ回と費用
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import statistics
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from PIL import Image
from temporalio import activity
from temporalio.exceptions import ApplicationError

import comfy_client
from harness_config import (CHARACTER_FIXED, DETECTOR_URL, DIFFUSION, EDGE_PX, LLM_EMPTY_DIR, NEGATIVE_FIXED,
                            REGISTRY_LOG, SCRATCH, STORE, STYLE_FIXED)
from v3server.comfy_graphs.image_to_image_graph import build_image_to_image
from v3server.comfy_graphs.model_loader_nodes import DiffusionSettings, Extras
from v3server.comfy_graphs.source_and_masks import PROTECTED_MASK, SOURCE
from v3server.comfy_graphs.text_to_image_graph import build_text_to_image_process
from v3server.judge_procedures.blind_image_copy import make_blind_copies

POSTS_LOG = SCRATCH / "prompt_posts.jsonl"
CLAUDE_LOG = SCRATCH / "claude_calls.jsonl"
EVAL_CACHE = SCRATCH / "eval_cache"


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"t": time.time(), **row}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _info() -> dict:
    i = activity.info()
    return {"workflow_id": i.workflow_id, "activity_attempt": i.attempt}


def _hb(**detail: Any) -> None:
    activity.heartbeat(detail)


# ---------------------------------------------------------------- 文脈を組む

@activity.defn
async def make_context(args: dict) -> dict:
    """設計 10章の 4：先頭は固定（画風・キャラの見た目）、中ほどは対象と直前の失敗、末尾は目標。
    画像生成に渡す語句はプログラムで組む。人の却下の理由（日本語）は作業役（Claude）に語句へ直させる。"""
    spec, adj = args["spec"], args["adjustments"]
    pos = [STYLE_FIXED, CHARACTER_FIXED, spec["variable"], *adj["add"]]
    neg = [NEGATIVE_FIXED, *adj["neg"]]
    cost, notes = 0.0, []
    for reason in args["human_reasons"]:
        r = await _reason_to_words(reason, spec, args["cache_key"])
        cost += r["cost"]
        if r["add"]:
            pos.append(r["add"])
        if r["remove"]:
            neg.append(r["remove"])
        notes.append({"reason": reason, "add": r["add"], "remove": r["remove"], "why": r["why"]})
    return {"positive": ", ".join(p for p in pos if p), "negative": ", ".join(n for n in neg if n),
            "cost_usd": cost, "reason_words": notes}


REASON_QUESTION = """漫画の1コマ用の絵を画像生成のモデル（Stable Diffusion 1.5）で作っています。人がその絵を見て、次の理由で却下しました。

コマの狙い：{target}
却下の理由：{reason}

理由を絵に反映させるため、画像生成の指示に足す英語の語句と、外したい物として渡す英語の語句を決めてください。
選べる手：
- 足す語句だけを書く（理由が「足りない物」を言っているとき）
- 外す語句だけを書く（理由が「余計な物」を言っているとき）
- 両方を書く
足す語句が多すぎると、コマの元の狙い（人数・写す範囲）が薄れて検査で落ちやすくなります。少なすぎると、理由が絵に出ず同じ却下が繰り返されます。
語句はカンマで区切った短い英語にしてください。どちらかが不要なら空の文字列にしてください。

出力はJSONだけにしてください。形式：{{"add":"足す語句","remove":"外す語句","why":"理由"}}"""


async def _reason_to_words(reason: str, spec: dict, cache_key: str) -> dict:
    key = f"reason-{uuid.uuid5(comfy_client.NS, cache_key + reason)}"
    cached = EVAL_CACHE / f"{key}.json"
    if cached.exists():
        return json.loads(cached.read_text())
    q = REASON_QUESTION.format(target=spec["target_ja"], reason=reason)
    d, cost = await _claude(q, [], "reason")
    out = {"add": str(d.get("add", "")), "remove": str(d.get("remove", "")), "why": str(d.get("why", "")), "cost": cost}
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(out, ensure_ascii=False))
    return out


# ---------------------------------------------------------------- 生成（候補1枚）

def _store_path(name: str) -> Path:
    return STORE / name


def _register(pid: str, data: bytes, unit: str, extra: dict) -> tuple[str, bool]:
    """置き場に名前 <pid>.png で置く。既にあれば置かない（同じ絵の二重登録を防ぐ）。
    書きかけを残さないため、一時の名前で書いてから名前を変える。"""
    name = f"{pid}.png"
    dest = _store_path(name)
    STORE.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        _append(REGISTRY_LOG, {"event": "already", "pid": pid, "unit": unit, **extra})
        return name, False
    tmp = dest.with_suffix(f".tmp{os.getpid()}")
    tmp.write_bytes(data)
    os.replace(tmp, dest)
    _append(REGISTRY_LOG, {"event": "registered", "pid": pid, "unit": unit, **extra})
    return name, True


@activity.defn
async def generate_candidate(args: dict) -> dict:
    """候補を1枚作って置き場に登録する。
    idempotent=True：依頼の番号を作業・回・候補から決め、同じ番号が ComfyUI にあれば送らずに待つ。
    idempotent=False：活動をやり直すたびに新しい番号で送る（今のサーバーの送り方に近い比べる用）。"""
    t0 = time.time()
    info = _info()
    pid = args["pid"] if args["idempotent"] else str(uuid.uuid4())
    d = json.loads(json.dumps(DIFFUSION))
    if args.get("unet_override"):
        d["model"]["unet_name"] = args["unet_override"]  # (b) の「内容で断られた」を作るため
    settings = DiffusionSettings.model_validate(d)
    base_url = args.get("comfy_url") or comfy_client.COMFY_URL
    prefix = f"p60_{args['unit']}"
    if args["mode"] == "t2i":
        prompt = build_text_to_image_process(settings, args["positive"], args["negative"], args["seed"],
                                             args["width"], args["height"], Extras(control=None), prefix).to_prompt()
    else:
        prompt = build_image_to_image(settings, args["positive"], args["negative"], args["seed"], args["strength"],
                                      (args["width"], args["height"]), Extras(control=None), prefix).to_prompt()
        prompt[SOURCE]["inputs"]["image"] = await comfy_client.upload_image(_store_path(args["source"]), f"p60_src_{args['source']}")
        prompt[PROTECTED_MASK]["inputs"]["image"] = await comfy_client.upload_image(
            _store_path(args["protected_mask"]), f"p60_mask_{args['protected_mask']}")
    stored_now = None
    state = {"s": "sending"}

    def on_wait(s: str) -> None:
        state["s"] = s
        _hb(comfy=s, prompt_id=pid, elapsed=round(time.time() - t0, 1))

    try:
        _hb(comfy="sending", prompt_id=pid)
        before_posts = _count_posts(pid)
        data, meta = await comfy_client.run_prompt(
            prompt, pid, on_wait, base_url, on_sent=lambda: _append(POSTS_LOG, {"pid": pid, "unit": args["unit"], **info}))
        name, new = _register(pid, data, args["unit"], {"attempt": args["attempt"], "cand": args["cand"], **info})
        stored_now = name if new else None
        _hb(comfy="registered", prompt_id=pid)
        return {"pid": pid, "image": name, "seconds": round(time.time() - t0, 2), "sent_now": meta["sent_now"],
                "activity_attempt": info["activity_attempt"], "posts_before": before_posts}
    except asyncio.CancelledError:
        # 取り消し：ComfyUI の依頼は comfy_client が消すか止めた。登録したばかりの絵は取り下げる
        if stored_now:
            _store_path(stored_now).unlink(missing_ok=True)
            _append(REGISTRY_LOG, {"event": "withdrawn", "pid": pid, "unit": args["unit"], **info})
        raise
    except comfy_client.ComfyError as e:
        retry = e.kind == "transport"
        raise ApplicationError(str(e), type=e.kind, non_retryable=not retry) from e


def _count_posts(pid: str) -> int:
    if not POSTS_LOG.exists():
        return 0
    return sum(1 for line in POSTS_LOG.read_text().splitlines() if json.loads(line)["pid"] == pid)


# ---------------------------------------------------------------- 検査

@activity.defn
async def run_checks(args: dict) -> dict:
    """答えが決まる検査を並べて掛ける。合格は1行、失敗だけ詳しく（設計 10章の 6）。
    検出器のプロセス（v3/detector_server）に送る。"""
    t0 = time.time()
    path = _store_path(args["image"])
    img = Image.open(path)
    results = []
    _hb(check="大きさ")
    ok = img.size == (args["width"], args["height"])
    results.append({"id": "size", "title": "大きさ", "status": "合格" if ok else "不合格",
                    "value": f"{img.size[0]}x{img.size[1]}"})
    _hb(check="人物の検出")
    url = args.get("detector_url") or DETECTOR_URL
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(url + "/person_face_head", files={"image": (path.name, path.read_bytes(), "image/png")},
                             data={"edge_px": str(EDGE_PX)})
    except httpx.HTTPError as e:
        raise ApplicationError(f"検出器に届かない: {e}", type="transport") from e
    if r.status_code >= 500:
        raise ApplicationError(f"検出器が {r.status_code}", type="transport")
    d = r.json()
    persons = d["persons"]
    n = len(persons)
    exp = args["expected_persons"]
    results.append({"id": "persons", "title": "人数", "status": "合格" if n == exp else "不合格",
                    "value": n, "detail": None if n == exp else f"{exp}人のはずが{n}人"})
    touch = sorted({ch for p in persons for ch in (p.get("touch") or "") if ch in "TB"})
    if args["full_body"]:
        _hb(check="見切れ")
        cut = bool(touch)
        results.append({"id": "cutoff", "title": "見切れ（全身のコマで上下の端に触れる）",
                        "status": "不合格" if cut else "合格", "value": "".join(touch) or "なし",
                        "detail": f"人物の枠が端 {''.join(touch)} に触れた" if cut else None})
    h_ratios = sorted((round(p["h_ratio"], 3) for p in persons), reverse=True)
    return {"results": results, "passed": all(x["status"] == "合格" for x in results),
            "persons": n, "touch": "".join(touch), "h_ratios": h_ratios,
            "seconds": round(time.time() - t0, 2)}


# ---------------------------------------------------------------- 評価役

EVAL_QUESTION = """添えた絵は、漫画の1コマ用に画像生成で作った試作の絵です。小さい試作なので、線の細かさや画質の低さは問いません。

コマの狙い：{target}
{extra}
この絵がコマの狙いにどれだけ合うかを、1から5の点で付けてください。
- 5：狙いの人数・写す範囲・内容がそろっている
- 4：小さなずれが1つある
- 3：ずれはあるが、このコマとして使える
- 2：狙いの一部（人数・写す範囲・内容のどれか）が合わない
- 1：狙いとほぼ関係が無い
3未満を付けると、この絵は捨てられて作り直しになり、時間がかかります。合わない絵に3以上を付けると、そのまま人の確認に進み、人が見て却下することになります。

出力はJSONだけにしてください。形式：{{"score":点の数,"why":"理由"}}"""


@activity.defn
async def evaluate(args: dict) -> dict:
    """評価役（Claude の CLI、sonnet）。同じ絵を repeats 回聞いて、ぶれを測る。
    評価役に作業役の説明は渡さない。見せるのは名前を伏せた写しと狙いだけ（設計 8.2）。
    1回ごとの答えは置いておき、活動がやり直されたら終わった分は呼び直さない。"""
    t0 = time.time()
    extra = ""
    if args.get("reasons"):
        extra = "人がこれまでに出した直しの理由（これも狙いに含めて判定してください）：" + "／".join(args["reasons"]) + "\n"
    q = EVAL_QUESTION.format(target=args["target_ja"], extra=extra)
    scores, whys, cost, calls = [], [], 0.0, 0
    for i in range(args["repeats"]):
        cached = EVAL_CACHE / f"eval-{args['key']}-{i}.json"
        if cached.exists():
            d = json.loads(cached.read_text())
        else:
            _hb(evaluate=f"{i + 1}/{args['repeats']}")
            blind_dir = LLM_EMPTY_DIR / "blind" / args["key"] / str(i)
            blind = make_blind_copies([str(_store_path(args["image"]))], str(blind_dir), salt=f"{args['key']}-{i}")
            bpath = str(next(iter(blind.blind_path_by_original.values())))
            ans, c = await _claude(q + f"\n\n絵のファイル：{bpath}", [bpath], "evaluate")
            try:
                score = int(ans["score"])
            except (KeyError, TypeError, ValueError) as e:
                raise ApplicationError(f"評価役の答えの形が崩れた: {ans}", type="broken_response", non_retryable=True) from e
            d = {"score": score, "why": str(ans.get("why", "")), "cost": c}
            calls += 1
            EVAL_CACHE.mkdir(parents=True, exist_ok=True)
            cached.write_text(json.dumps(d, ensure_ascii=False))
        scores.append(d["score"])
        whys.append(d["why"])
        cost += d["cost"]
    return {"scores": scores, "median": statistics.median(scores), "spread": max(scores) - min(scores),
            "whys": whys, "cost_usd": round(cost, 4), "calls": calls, "seconds": round(time.time() - t0, 2)}


async def _claude(question: str, images: list[str], purpose: str) -> tuple[dict, float]:
    """Claude の CLI を空のフォルダで呼ぶ。取り消されたらプロセスを止める。"""
    LLM_EMPTY_DIR.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_REMOTE_SESSION_ID", "CLAUDECODE")}
    cmd = ["claude", "-p", "--model", "sonnet", "--output-format", "json", "--no-session-persistence", "--max-turns", "4"]
    if images:
        cmd += ["--allowedTools", "Read"]
    t0 = time.time()
    proc = await asyncio.create_subprocess_exec(*cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.PIPE, cwd=str(LLM_EMPTY_DIR), env=env)
    comm = asyncio.ensure_future(proc.communicate(question.encode()))
    try:
        while not comm.done():
            _hb(claude=purpose, elapsed=round(time.time() - t0, 1))
            await asyncio.wait([comm], timeout=1.0)
        out, err = comm.result()
    except asyncio.CancelledError:
        proc.kill()
        _append(CLAUDE_LOG, {"purpose": purpose, "killed": True, "seconds": round(time.time() - t0, 1), **_info()})
        raise
    if proc.returncode != 0:
        raise ApplicationError(f"claude が {proc.returncode}: {err.decode()[:300]}", type="transport")
    res = json.loads(out)
    cost = float(res.get("total_cost_usd") or 0.0)
    _append(CLAUDE_LOG, {"purpose": purpose, "cost": cost, "seconds": round(time.time() - t0, 1), **_info()})
    text = res.get("result", "")
    s, e = text.find("{"), text.rfind("}")
    if s < 0 or e < 0:
        raise ApplicationError(f"答えに JSON が無い: {text[:200]}", type="broken_response", non_retryable=True)
    try:
        return json.loads(text[s:e + 1]), cost
    except json.JSONDecodeError as ex:
        raise ApplicationError(f"答えの JSON が崩れた: {text[:200]}", type="broken_response", non_retryable=True) from ex


# ---------------------------------------------------------------- 版の確定・後片付け

@activity.defn
async def register_version(args: dict) -> dict:
    """採用した候補を版として確定する。同じ作業・同じ版の番号で2回呼ばれても1回だけ書く。"""
    vdir = STORE / "versions"
    vdir.mkdir(parents=True, exist_ok=True)
    dest = vdir / f"{args['unit']}_v{args['version']}.png"
    if dest.exists():
        _append(REGISTRY_LOG, {"event": "version_already", "unit": args["unit"], "version": args["version"], **_info()})
        return {"version_image": f"versions/{dest.name}", "new": False}
    tmp = dest.with_suffix(".tmp")
    shutil.copyfile(_store_path(args["image"]), tmp)
    os.replace(tmp, dest)
    _append(REGISTRY_LOG, {"event": "version", "unit": args["unit"], "version": args["version"], "image": args["image"], **_info()})
    return {"version_image": f"versions/{dest.name}", "new": True}


@activity.defn
async def cleanup_unit(args: dict) -> dict:
    """作業を取り消したときの後片付け。その作業の番号の依頼を ComfyUI から消すか止める。
    置き場にあるがワークフローの候補に載っていない絵は取り下げる。"""
    res = await comfy_client.cancel_prompts(args["prompt_ids"])
    withdrawn = 0
    for pid in args["prompt_ids"]:
        p = _store_path(f"{pid}.png")
        if p.exists() and f"{pid}.png" not in args["known_images"]:
            p.unlink()
            withdrawn += 1
            _append(REGISTRY_LOG, {"event": "withdrawn", "pid": pid, "unit": args["unit"], **_info()})
    return {**res, "withdrawn": withdrawn}


# ---------------------------------------------------------------- ネームの検査・ページの検査

@activity.defn
async def name_check(args: dict) -> dict:
    """S3 ネーム：v3/server の name_checks をそのまま掛ける。"""
    from p60_page import run_page_name_checks
    return run_page_name_checks(args["panels"], measured=None)


@activity.defn
async def page_check(args: dict) -> dict:
    """S6 総合：描けた絵から測った人数で、同じネームの検査を掛け直す。ページの絵も組む（S7 の代わり）。"""
    from p60_page import compose_page, run_page_name_checks
    rep = run_page_name_checks(args["panels"], measured=args["measured"])
    page = compose_page(args["images"], STORE / "pages" / f"{args['stage']}.png")
    return {**rep, "page_image": f"pages/{page.name}"}


def protected_diff(before: str, after: str, mask: str) -> dict:
    """人の手の範囲（マスクの白）で、前と後の画素がいくつ変わったか。範囲の外も数える。"""
    a = np.asarray(Image.open(_store_path(before)).convert("RGB"), dtype=np.int16)
    b = np.asarray(Image.open(_store_path(after)).convert("RGB"), dtype=np.int16)
    m = np.asarray(Image.open(_store_path(mask)).convert("L")) > 127
    changed = np.abs(a - b).max(axis=2) > 0
    return {"inside_changed": int((changed & m).sum()), "inside_total": int(m.sum()),
            "outside_changed": int((changed & ~m).sum()), "outside_total": int((~m).sum())}


ALL = [make_context, generate_candidate, run_checks, evaluate, register_version, cleanup_unit, name_check, page_check]
