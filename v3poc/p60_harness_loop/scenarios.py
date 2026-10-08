"""P60 の場面 b〜s（run.py から呼ぶ）。
b：止まるか（上限回数・費用・時間・エラーの連続・内容で断られた・上限を動いている間に変える）
c：作業者を落とす（生成・検査・評価・判断待ち）と Temporal の再起動。重複の生成を数える
d：判断待ちの人の操作（却下と理由・人の直し・上流の変更）
i：各段での割り込み（一時停止と再開・1段の取り消し・上流の変更・作業の取り消し・工程の取り消し）
s：1ページ3コマの工程を画面と一緒に流し、画面の絵を撮る
e：ComfyUI の履歴から実行の時間と順番待ちの時間を取る
collect：out/result.json にまとめる
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from temporalio.client import WorkflowUpdateFailedError

import infra
from harness_activities import POSTS_LOG, protected_diff
from harness_config import (API_PORT, COMFY_URL, DEFAULT_LIMITS, HEIGHT, HERE, LLM_EMPTY_DIR, OUT, PANELS, SCRATCH,
                            STORE, TASK_QUEUE, WIDTH)
from run import (RUN_TAG, _lines, awaiting, brief, client, comfy_queue, counts_for, finished, log, orphans,
                 running_on, save_part, st, start, store_orphans, unit_input, wait_for)

T = RUN_TAG


def uid(name: str) -> str:
    return f"{name}-{T}"


async def refused_update(h, name: str, arg: dict) -> str | None:
    """検証で弾かれたら理由を返す。通ったら None。"""
    try:
        await h.execute_update(name, arg)
        return None
    except WorkflowUpdateFailedError as e:
        return str(e.cause.message if e.cause else e)


async def hist_len(h) -> int:
    return (await h.describe()).history_length


# ================================================================ b

async def scenario_b() -> None:
    out = {}
    # b1 上限回数。評価役の合格点を 6（付けられない点）にして、評価役が必ず不合格にする
    h1 = await start(unit_input(uid("b1"), 3, seed=501, eval_min_score=6, max_attempts=1, candidates_per_attempt=1,
                                eval_repeats=1))
    s, _ = await wait_for(h1, awaiting, what="上限回数で判断待ち")
    rec = {"first_stop": s["stop_reason"], "round_attempts": s["round_attempts"]}
    hl0 = await hist_len(h1)
    rec["raise_to_2"] = await refused_update(h1, "set_limits", {"max_attempts": 2})
    s, _ = await wait_for(h1, lambda s, d: awaiting(s, d) and s["round_attempts"] >= 2, what="2回目の後の判断待ち")
    rec["second_stop"] = s["stop_reason"]
    hl1 = await hist_len(h1)
    rec["lower_to_1_refused"] = await refused_update(h1, "set_limits", {"max_attempts": 1})
    rec["budget_below_used_refused"] = await refused_update(h1, "set_limits", {"budget_usd": 0.0})
    rec["unknown_limit_refused"] = await refused_update(h1, "set_limits", {"no_such": 1})
    hl2 = await hist_len(h1)
    rec["history_len"] = {"before_raise": hl0, "after_second_stop": hl1, "after_3_refused": hl2}
    rec["approve"] = await refused_update(h1, "review", {"action": "approve"})
    r, status = await finished(h1)
    rec.update(result=r, status=status, state=brief(await st(h1)))
    out["b1_attempt_cap_and_limits"] = rec
    log("(b1)", rec["first_stop"], rec["second_stop"], rec["lower_to_1_refused"], status)

    # b2 費用の上限・b3 時間の上限・b4 通信の失敗の連続・b5 内容で断られた（どれも判断待ちを置かず、止まったら終わる）
    cases = {
        "b2_budget_usd": (unit_input(uid("b2"), 3, seed=502, review="none", budget_usd=0.03, eval_repeats=1,
                                     candidates_per_attempt=1), {}),
        "b3_budget_seconds": (unit_input(uid("b3"), 3, seed=503, review="none", budget_seconds=5, eval_repeats=1,
                                         candidates_per_attempt=1), {}),
        "b4_transport_errors": (unit_input(uid("b4"), 3, seed=504, review="none", resend_limit=1, error_stop=3,
                                           candidates_per_attempt=1, max_attempts=10),
                                {"comfy_url": "http://127.0.0.1:63299"}),
        "b5_refused": (unit_input(uid("b5"), 3, seed=505, review="none", candidates_per_attempt=1, max_attempts=10),
                       {"unet_override": "no_such_unet.safetensors"}),
    }
    hs = {}
    for k, (inp, extra) in cases.items():
        hs[k] = (await start(inp, **extra), time.time())
    for k, (h, t0) in hs.items():
        r, status = await finished(h)
        s = await st(h)
        out[k] = {"result": r, "status": status, "seconds": round(time.time() - t0, 1), "state": brief(s),
                  "errors_in_row": s["errors_in_row"], "last_error": s.get("last_error")}
        log(f"({k})", r.get("reason"), status)
    out["counts"] = counts_for([uid(x) for x in ("b1", "b2", "b3", "b4", "b5")])
    save_part("b", out)


# ================================================================ c

async def kill_and_restart(pause_s: float = 3.0) -> dict:
    t0 = time.time()
    infra.kill_worker(hard=True)
    await asyncio.sleep(pause_s)
    infra.start_worker()
    return {"down_seconds": round(time.time() - t0, 1)}


async def node_done_after(h, node: str, count: int, timeout=1800) -> float:
    t0 = time.time()
    await wait_for(h, lambda s, d: s["nodes"][node]["count"] >= count and s["nodes"][node]["status"] in
                   ("done", "failed") or s["status"] == "awaiting_review", timeout=timeout, what=f"{node} の終わり")
    return round(time.time() - t0, 1)


async def scenario_c() -> None:
    out = {}
    u = uid("c1")
    hist0 = await (__import__("comfy_client").history_count())
    h = await start(unit_input(u, 3, seed=601, candidates_per_attempt=1, eval_repeats=2))
    steps = {}
    for node, comfy in (("generate", "running"), ("check", None), ("evaluate", None)):
        try:
            s, d = await wait_for(h, running_on(node, comfy), timeout=1200, what=f"{node} の実行中")
        except (TimeoutError, RuntimeError) as e:
            steps[node] = {"missed": str(e)}
            continue
        cnt = s["nodes"][node]["count"]
        k = await kill_and_restart()
        k["recovered_after_s"] = await node_done_after(h, node, cnt)
        steps[node] = k
        log("(c1)", node, k)
    s, _ = await wait_for(h, awaiting, what="判断待ち")
    before = {"status": s["status"], "review_reason": s["review_reason"], "candidates": len(s["candidates"])}
    # 判断待ちのまま、作業者と Temporal の両方を止めて起動し直す
    t0 = time.time()
    infra.kill_worker(hard=True)
    infra.stop_temporal(remove=False)
    await asyncio.sleep(2)
    infra.start_temporal(fresh=False)
    infra.start_worker()
    import run as runmod
    runmod._client = None
    h = (await client()).get_workflow_handle(u)
    s2 = await st(h)
    after = {"status": s2["status"], "review_reason": s2["review_reason"], "candidates": len(s2["candidates"]),
             "restart_seconds": round(time.time() - t0, 1)}
    steps["review_wait_restart"] = {"before": before, "after": after}
    approve = await refused_update(h, "review", {"action": "approve"})
    r, status = await finished(h)
    out["c1_idempotent"] = {"steps": steps, "approve": approve, "result": r, "status": status,
                            "state": brief(await st(h)), "counts": counts_for([u])}
    log("(c1)", status, out["c1_idempotent"]["counts"])

    # c2 依頼の番号を活動のやり直しごとに変える（今のサーバーに近い）と、落としたときに二重に作るか
    u2 = uid("c2")
    h2 = await start(unit_input(u2, 3, seed=602, review="none", eval_enabled=False, candidates_per_attempt=1,
                                max_attempts=1, idempotent=False))
    s, d = await wait_for(h2, running_on("generate", "running"), what="生成の実行中")
    k = await kill_and_restart()
    r, status = await finished(h2)
    hist1 = await (__import__("comfy_client").history_count())
    out["c2_not_idempotent"] = {"kill": k, "result": r, "status": status, "state": brief(await st(h2)),
                                "counts": counts_for([u2])}
    out["comfy_history_delta_c1_c2"] = hist1 - hist0
    out["orphans_after"] = await orphans()
    log("(c2)", status, out["c2_not_idempotent"]["counts"])
    save_part("c", out)


# ================================================================ d

YESNO = """添えた絵について答えてください。
問い：{q}
選べる答え：「はい」「いいえ」「判断できない」。絵だけから言えないときに「はい」か「いいえ」を選ぶと、試作の測定が誤ります。
出力はJSONだけにしてください。形式：{{"answer":"はい か いいえ か 判断できない","why":"理由"}}"""


def ask_yesno(image: Path, q: str) -> dict:
    """試作の測る側の質問（作業の評価役とは別に、測定のために聞く）。"""
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_REMOTE_SESSION_ID", "CLAUDECODE")}
    blind = LLM_EMPTY_DIR / "measure" / f"{abs(hash((str(image), q))) % 10**8}.png"
    blind.parent.mkdir(parents=True, exist_ok=True)
    blind.write_bytes(image.read_bytes())
    r = subprocess.run(["claude", "-p", "--model", "sonnet", "--output-format", "json", "--no-session-persistence",
                        "--allowedTools", "Read", "--max-turns", "4"],
                       input=YESNO.format(q=q) + f"\n\n絵のファイル：{blind}", capture_output=True, text=True,
                       cwd=str(LLM_EMPTY_DIR), env=env, timeout=300)
    res = json.loads(r.stdout)
    text = res.get("result", "")
    d = json.loads(text[text.find("{"): text.rfind("}") + 1])
    return {"answer": d.get("answer"), "why": d.get("why"), "cost": res.get("total_cost_usd")}


def make_human_edit(src: str, tag: str) -> tuple[str, str]:
    """人の直しの代わりに、試作のスクリプトで左上の範囲に線を描き込む（人が描いた物ではない）。
    範囲のマスク（白が人の手）も作る。"""
    im = Image.open(STORE / src).convert("RGB")
    w, h = im.size
    box = (0, 0, int(w * 0.45), int(h * 0.45))
    d = ImageDraw.Draw(im)
    d.rectangle(box, fill=(250, 248, 240))
    rng = np.random.default_rng(7)
    for _ in range(40):
        x0, y0 = rng.integers(4, box[2] - 4), rng.integers(4, box[3] - 4)
        x1, y1 = rng.integers(4, box[2] - 4), rng.integers(4, box[3] - 4)
        d.line((int(x0), int(y0), int(x1), int(y1)), fill=(30, 30, 30), width=2)
    edited = f"human_edit_{tag}.png"
    im.save(STORE / edited)
    m = Image.new("RGB", (w, h), "black")
    ImageDraw.Draw(m).rectangle(box, fill="white")
    mask = f"human_mask_{tag}.png"
    m.save(STORE / mask)
    return edited, mask


async def scenario_d() -> None:
    out = {}
    u = uid("d2")
    h = await start(unit_input(u, 3, seed=701, candidates_per_attempt=1, eval_repeats=1, review_notify_seconds=5))
    s, _ = await wait_for(h, awaiting, what="1回目の判断待ち")
    await asyncio.sleep(7)
    s = await st(h)
    overdue = [e for e in s["events"] if e["kind"] == "review_overdue"]
    best1 = next((c for c in s["candidates"] if c["id"] == s["best"]), s["candidates"][-1])
    reason = "背景を夜の街にしてほしい"
    rej = await refused_update(h, "review", {"action": "reject", "reason": reason})
    s, _ = await wait_for(h, lambda s, d: awaiting(s, d) and s["round"] == 2, what="却下後の判断待ち")
    best2 = next((c for c in s["candidates"] if c["id"] == s["best"]), s["candidates"][-1])
    q = "この絵の背景は夜の街ですか"
    m1, m2 = ask_yesno(STORE / best1["image"], q), ask_yesno(STORE / best2["image"], q)
    out["d2_reject_with_reason"] = {"stop_reason_1": brief(s)["stop_reason"], "overdue_events": len(overdue),
                                    "reject": rej, "reason_words": s.get("last_context", {}).get("reason_words"),
                                    "before": {"image": best1["image"], "measure": m1},
                                    "after": {"image": best2["image"], "eval": best2.get("eval"), "measure": m2}}
    log("(d2)", m1["answer"], "→", m2["answer"])
    # 空の理由の却下は弾かれる
    out["d2_reject_empty_refused"] = await refused_update(h, "review", {"action": "reject", "reason": " "})

    # d3 人の直し：直した絵を登録して検査・評価を掛け直し、そのあと却下で作り直す。人の手の範囲が残るか
    edited, mask = make_human_edit(best2["image"], u)
    e1 = await refused_update(h, "review", {"action": "edit", "edited_image": edited, "protected_mask": mask})
    s, _ = await wait_for(h, lambda s, d: awaiting(s, d) and s["review_reason"] == "人の直しを検査した",
                          what="人の直しの検査")
    hc = next(c for c in s["candidates"] if c["source"] == "human")
    e2 = await refused_update(h, "review", {"action": "reject", "reason": "人が描いた所はそのままにして、残りの絵を整えてほしい"})
    s, _ = await wait_for(h, lambda s, d: awaiting(s, d) and s["round"] == 3, what="人の直しの後の作り直し")
    new = [c for c in s["candidates"] if c.get("mode") == "i2i"]
    diffs = [{"id": c["id"], **protected_diff(edited, c["image"], mask)} for c in new]
    out["d3_human_edit"] = {"edit": e1, "human_candidate": {"check": hc.get("check"), "eval": hc.get("eval")},
                            "reject_after_edit": e2, "i2i_candidates": len(new), "protected_diff": diffs,
                            "edited": edited, "mask": mask}
    log("(d3)", diffs)
    out["d_approve"] = await refused_update(h, "review", {"action": "approve"})
    r, status = await finished(h)
    out["d2_state"] = brief(await st(h))
    out["d2_status"] = status

    # d4 判断待ちの間に上流が変わる
    u4 = uid("d4")
    h4 = await start(unit_input(u4, 3, seed=702, candidates_per_attempt=1, eval_repeats=1))
    s, _ = await wait_for(h4, awaiting, what="判断待ち")
    await h4.signal("upstream_changed", {"spec": {"variable": "1girl, solo, upper body, surprised face, rain",
                                                  "target_ja": "雨の中で驚いた顔の少女1人。胸から上"},
                                         "what": "ネームのコマ3の中身"})
    await asyncio.sleep(2)
    s = await st(h4)
    stale = [c["id"] for c in s["candidates"] if c["stale"]]
    approve_refused = await refused_update(h4, "review", {"action": "approve"})
    rej = await refused_update(h4, "review", {"action": "reject", "reason": "上流の変更に合わせる"})
    s, _ = await wait_for(h4, lambda s, d: awaiting(s, d) and s["round"] == 2, what="上流の変更の後の判断待ち")
    fresh = [c["id"] for c in s["candidates"] if not c["stale"]]
    ok = await refused_update(h4, "review", {"action": "approve"})
    r, status = await finished(h4)
    out["d4_upstream_while_waiting"] = {"stale_after_signal": stale, "approve_refused": approve_refused,
                                        "reject": rej, "fresh_after": fresh, "approve_after": ok, "status": status}
    out["counts"] = counts_for([u, u4])
    out["orphans_after"] = await orphans()
    save_part("d", out)


# ================================================================ i

async def comfy_has(pids: list[str]) -> bool:
    q = await comfy_queue()
    return any(p in q["running"] + q["pending"] for p in pids)


async def interrupt_at(h, node: str, do, until, comfy: str | None = None, timeout=1500) -> dict:
    """node が走っている間に do(h) を送り、until(s, d) まで待つ。送ってから止まるまでの時間と、
    ComfyUI に残った依頼を数える。"""
    try:
        s, d = await wait_for(h, running_on(node, comfy), timeout=timeout, what=f"{node} の実行中")
    except (TimeoutError, RuntimeError) as e:
        return {"missed": str(e)}
    pids = (s.get("inflight") or {}).get("pids") or []
    n_ev = len(s["events"])
    t0 = time.time()
    await do(h)
    s2, d2 = await wait_for(h, lambda s, d: until(s, d, n_ev), timeout=600, what=f"{node} の割り込みの後")
    dt = round(time.time() - t0, 2)
    await asyncio.sleep(1.5)
    left = await comfy_has(pids)
    return {"node": node, "settled_seconds": dt, "node_status": s2["nodes"][node]["status"],
            "unit_status": s2["status"], "comfy_prompt_left": left, "pids": pids,
            "events_after": [f"{e['node']}:{e['kind']}" for e in s2["events"][n_ev:]][:12]}


def node_is(node: str, *sts):
    """割り込みを送った後の出来事に、その段の sts のどれかが出たら。"""
    return lambda s, d, n: any(e["node"] == node and e["kind"] in sts for e in s["events"][n:]) or d.status.name != "RUNNING"


def review_after(s, d, n) -> bool:
    return any(e["kind"] == "awaiting_review" for e in s["events"][n:])


async def scenario_i() -> None:
    out = {}
    # 一時停止と再開（mode=now は走っている段を取り消して止め、再開でその段からやり直す）
    u = uid("ip")
    h = await start(unit_input(u, 3, seed=801, candidates_per_attempt=1, eval_repeats=2))
    res = {}
    for node, comfy in (("generate", "running"), ("check", None), ("evaluate", None)):
        # 段が先に終われば次の段の始まりで止まる（取り消しは生存の知らせで届くので、短い段は間に合わない）
        r = await interrupt_at(h, node, lambda h: h.signal("pause", "now"),
                               lambda s, d, n: any(e["kind"] == "paused" for e in s["events"][n:]) or d.status.name != "RUNNING",
                               comfy)
        await asyncio.sleep(2)
        t0 = time.time()
        await h.signal("resume")
        if "missed" not in r:
            r["resumed_done_after_s"] = await node_done_after(h, node, 1)
        r["resume_sent_at"] = t0
        res[node] = r
        log("(i pause)", node, r)
    s, _ = await wait_for(h, awaiting, what="判断待ち")
    await h.signal("pause", "now")
    await asyncio.sleep(1)
    s = await st(h)
    res["review"] = {"paused_flag": s["paused"], "status": s["status"],
                     "approve_while_paused": await refused_update(h, "review", {"action": "approve"})}
    await h.signal("resume")
    r, status = await finished(h)
    out["pause_resume"] = {"steps": res, "status": status, "state": brief(await st(h)), "counts": counts_for([u])}

    # 1段の取り消し（生成は候補を1枚捨てて次へ。検査はその候補を判定できない扱い。評価は「判定できない観点がある」で判断待ちへ）
    u = uid("is")
    h = await start(unit_input(u, 3, seed=802, candidates_per_attempt=2, eval_repeats=1, max_attempts=3))
    res = {}
    res["generate"] = await interrupt_at(h, "generate", lambda h: h.signal("cancel_step"),
                                         node_is("generate", "cancelled", "done"), "running")
    res["limits_k_to_1"] = await refused_update(h, "set_limits", {"candidates_per_attempt": 1})
    res["check"] = await interrupt_at(h, "check", lambda h: h.signal("cancel_step"), node_is("check", "cancelled", "done"))
    res["evaluate"] = await interrupt_at(h, "evaluate", lambda h: h.signal("cancel_step"),
                                         node_is("evaluate", "cancelled", "done"), timeout=2400)
    s, _ = await wait_for(h, awaiting, what="判断待ち")
    res["review_reason"] = s["review_reason"]
    res["approve"] = await refused_update(h, "review", {"action": "approve"})
    r, status = await finished(h)
    out["cancel_step"] = {"steps": res, "status": status, "state": brief(await st(h)), "counts": counts_for([u])}
    log("(i step)", res)

    # 上流の変更を各段で
    u = uid("iu")
    h = await start(unit_input(u, 3, seed=803, candidates_per_attempt=1, eval_repeats=1))
    res = {}
    variants = ["1girl, solo, upper body, surprised face, classroom", "1girl, solo, upper body, surprised face, park",
                "1girl, solo, upper body, surprised face, beach"]
    for i, (node, comfy) in enumerate((("generate", "running"), ("check", None), ("evaluate", None))):
        ch = {"spec": {"variable": variants[i]}, "what": f"ネームの変更 {i + 1}"}
        r = await interrupt_at(h, node, lambda h, ch=ch: h.signal("upstream_changed", ch), review_after, comfy)
        s = await st(h)
        r["review_reason"] = s["review_reason"]
        r["stale_candidates"] = [c["id"] for c in s["candidates"] if c["stale"]]
        r["approve_refused"] = await refused_update(h, "review", {"action": "approve"})
        r["reject"] = await refused_update(h, "review", {"action": "reject", "reason": "上流の変更に合わせる"})
        res[node] = r
        log("(i upstream)", node, r.get("settled_seconds"), r.get("comfy_prompt_left"))
    s, _ = await wait_for(h, lambda s, d: awaiting(s, d) and s["round"] == 4, what="最後の判断待ち")
    res["final_approve"] = await refused_update(h, "review", {"action": "approve"})
    if res["final_approve"] is not None:  # 採用できる候補が無い（検査が全部不合格）ときは作業を取り消して終える
        await h.cancel()
    r, status = await finished(h)
    out["upstream_each_step"] = {"steps": res, "status": status, "state": brief(await st(h)), "counts": counts_for([u])}

    # 作業ごとの取り消しを各段で。検査・評価・判断待ちの作業は ip と同じ中身と seed にして、生成を ComfyUI の再利用で速くする
    res = {}
    for node, seed, comfy in (("generate", 804, "running"), ("check", 801, None), ("evaluate", 801, None),
                              ("review", 801, None)):
        uu = uid(f"ic-{node}")
        hh = await start(unit_input(uu, 3, seed=seed, candidates_per_attempt=1, eval_repeats=2))
        if node == "review":
            await wait_for(hh, awaiting, what="判断待ち")
            t0 = time.time()
            await hh.cancel()
            r, status = await finished(hh)
            rr = {"settled_seconds": round(time.time() - t0, 2), "status": status}
        else:
            rr = await interrupt_at(hh, node, lambda h: h.cancel(), lambda s, d, n: d.status.name != "RUNNING", comfy)
            r, status = await finished(hh)
            rr["status"] = status
        s = await st(hh)
        rr["cleanup"] = [e["detail"] for e in s["events"] if e["kind"] == "cleanup"]
        rr["store_orphans"] = store_orphans([uu], {uu: s})
        rr["counts"] = counts_for([uu])
        res[node] = rr
        log("(i cancel)", node, rr.get("status"), rr.get("comfy_prompt_left"), rr["store_orphans"])
    out["cancel_unit_each_step"] = res

    # 工程ごとの取り消し（3コマの生成中）
    c = await client()
    sid = uid("istage")
    hs = await c.start_workflow("StageWorkflow", stage_input(sid, review="none", eval_enabled=False, k=1),
                                id=sid, task_queue=TASK_QUEUE)
    await wait_child_generating(sid)
    t0 = time.time()
    await hs.cancel()
    r, status = await finished(hs)
    kids = {}
    for p in PANELS:
        ch = c.get_workflow_handle(f"{sid}-p{p['panel']}")
        d = await ch.describe()
        s = await st(ch)
        kids[ch.id] = {"status": d.status.name, "cleanup": [e["detail"] for e in s["events"] if e["kind"] == "cleanup"],
                       "store_orphans": store_orphans([ch.id], {ch.id: s})}
    await asyncio.sleep(2)
    out["cancel_stage"] = {"stage_status": status, "settled_seconds": round(time.time() - t0, 2), "children": kids,
                           "orphans": await orphans(), "counts": counts_for(list(kids))}
    log("(i stage cancel)", status, kids)
    save_part("i", out)


def stage_input(sid: str, review="human", eval_enabled=True, k=2, **lim) -> dict:
    return {"stage_id": sid, "panels": [dict(p) for p in PANELS], "limits": {**DEFAULT_LIMITS, "candidates_per_attempt": k, **lim},
            "mode": "guided", "review": review, "eval_enabled": eval_enabled, "base_seed": 900, "width": WIDTH,
            "height": HEIGHT, "requester": "試作の進行役"}


async def wait_child_generating(sid: str, timeout=1800) -> str:
    c = await client()
    t0 = time.time()
    while time.time() - t0 < timeout:
        for p in PANELS:
            ch = c.get_workflow_handle(f"{sid}-p{p['panel']}")
            try:
                s = await st(ch)
                d = await ch.describe()
            except Exception:
                continue
            if running_on("generate", "running")(s, d):
                return ch.id
        await asyncio.sleep(1)
    raise TimeoutError("子の生成が始まらない")


# ================================================================ s

def shoot(name: str, query: str, op: str = "") -> dict:
    env = {**os.environ, "PLAYWRIGHT_BROWSERS_PATH": "/opt/pw-browsers", "P60_CDN": str(SCRATCH / "cdn"),
           "P60_API_PORT": str(API_PORT)}
    r = subprocess.run(["node", str(HERE / "shoot.mjs"), name, query, op], capture_output=True, text=True, env=env,
                       timeout=180)
    log("撮った", name, r.stdout.strip()[-300:], r.stderr.strip()[-300:])
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"error": r.stderr[-500:]}


async def scenario_s() -> None:
    c = await client()
    sid = uid("stage")
    q = f"?stage={sid}"
    t0 = time.time()
    hs = await c.start_workflow("StageWorkflow", stage_input(sid, k=2, max_attempts=3, eval_repeats=2), id=sid,
                                task_queue=TASK_QUEUE)
    shots = {}
    await wait_child_generating(sid)
    await asyncio.sleep(4)
    shots["graph_running"] = shoot("graph_running", q)
    # 工程ごとの一時停止と再開
    await hs.signal("pause", "now")
    ok = False
    for _ in range(120):
        sts = [await st(c.get_workflow_handle(f"{sid}-p{p['panel']}")) for p in PANELS]
        if all(s["paused"] for s in sts) and not any(s["nodes"][s["current_node"]]["status"] in ("running", "cancelling") for s in sts):
            ok = True
            break
        await asyncio.sleep(0.5)
    pause_q = await comfy_queue()
    shots["paused"] = shoot("stage_paused", q)
    await hs.signal("resume")
    stage_pause = {"all_children_paused": ok, "comfy_queue_while_paused": pause_q}
    # 判断待ちを撮る
    first = None
    while first is None:
        for p in PANELS:
            ch = c.get_workflow_handle(f"{sid}-p{p['panel']}")
            s = await st(ch)
            if s["status"] == "awaiting_review":
                first = ch.id
                break
        await asyncio.sleep(2)
    await asyncio.sleep(2)
    shots["review_wait"] = shoot("review_wait", q)
    shots["node_detail"] = shoot("node_detail", q, f"detail={first}:check")
    approved = []
    while (await hs.describe()).status.name == "RUNNING":
        waiting = []
        for p in PANELS:
            s = await st(c.get_workflow_handle(f"{sid}-p{p['panel']}"))
            if s["status"] == "awaiting_review":
                waiting.append(s["unit_id"])
        if waiting:
            r = shoot(f"approve_{len(approved)}", q, "approve")
            approved.append({"waiting": waiting, "shot": r})
        await asyncio.sleep(5)
    r, status = await finished(hs)
    await asyncio.sleep(3)
    shots["stage_done"] = shoot("stage_done", q)
    units = {}
    for p in PANELS:
        ch = c.get_workflow_handle(f"{sid}-p{p['panel']}")
        units[ch.id] = {**brief(await st(ch)), "history_length": (await ch.describe()).history_length}
    save_part("s", {"stage": sid, "status": status, "result": r, "seconds": round(time.time() - t0, 1),
                    "stage_state": (await st(hs))["stages"], "stage_pause": stage_pause, "approved_via_screen": approved,
                    "units": units, "shots": shots, "counts": counts_for(list(units)),
                    "orphans": await orphans()})


# ================================================================ e と collect

async def scenario_e() -> None:
    """ComfyUI の履歴の時刻から、1枚の実行の時間を取る（順番待ちの時間は活動の時間から引く）。"""
    import httpx
    posts = _lines(POSTS_LOG)
    async with httpx.AsyncClient(base_url=COMFY_URL, timeout=30) as cl:
        hist = (await cl.get("/history?max_items=100000")).json()
    rows = []
    for p in posts:
        e = hist.get(p["pid"])
        if not e:
            continue
        msgs = {m[0]: m[1].get("timestamp") for m in e.get("status", {}).get("messages", [])}
        if "execution_start" in msgs and ("execution_success" in msgs or "execution_interrupted" in msgs):
            end = msgs.get("execution_success") or msgs.get("execution_interrupted")
            cached = sum(1 for m in e["status"]["messages"] if m[0] == "execution_cached" and m[1].get("nodes"))
            rows.append({"pid": p["pid"], "unit": p["unit"], "exec_seconds": round((end - msgs["execution_start"]) / 1000, 2),
                         "status": e["status"]["status_str"], "cached_nodes_msgs": cached})
    save_part("e", {"executions": rows})


def collect() -> None:
    parts = {p.stem[5:]: json.loads(p.read_text()) for p in sorted(OUT.glob("part_*.json"))}
    res = {"settings": {"width": WIDTH, "height": HEIGHT, "limits_default": DEFAULT_LIMITS,
                        "model": "SD1.5（UNet・文の符号化・VAE を分けた fp16）CPU", "evaluator": "Claude CLI sonnet",
                        "comfy_for_a": "本物の ComfyUI 0.39.2（CPU）",
                        "comfy_for_b_to_s": "【モック】mock_comfy.py（口だけ ComfyUI と同じ。絵は (a) の本物の絵から選ぶ。"
                                            "1段 3 秒×8段）。絵の良し悪しに関わる数は未検証"},
           "parts": parts}
    # (e) 段ごとの時間（全部の作業の state の nodes から）
    per_node: dict[str, list[float]] = {}
    for part in parts.values():
        for v in _walk_states(part):
            for n, nd in v.get("nodes", {}).items():
                if nd["count"]:
                    per_node.setdefault(n, []).append(nd["total_s"] / nd["count"])
    res["node_seconds_mean_per_run"] = {n: round(float(np.mean(v)), 2) for n, v in per_node.items()}
    ex = parts.get("e", {}).get("executions", [])
    real = [r["exec_seconds"] for r in ex if r["status"] == "success" and r["exec_seconds"] > 3]
    res["comfy_exec_seconds"] = {"n": len(real), "median": float(np.median(real)) if real else None,
                                 "min": min(real) if real else None, "max": max(real) if real else None}
    # 評価役のぶれ（同じ絵を2回聞いた点の差）
    spreads = []
    for part in parts.values():
        for v in _walk_states(part):
            for cnd in v.get("candidates", []):
                if cnd.get("eval") and len(cnd["eval"]["scores"]) >= 2:
                    spreads.append(max(cnd["eval"]["scores"]) - min(cnd["eval"]["scores"]))
    res["eval_spread"] = {"n": len(spreads), "same": spreads.count(0), "diff1": spreads.count(1),
                          "diff2plus": sum(1 for x in spreads if x >= 2)}
    # ComfyUI 側で実行された数（作業ごと）。送った記録は作業者が落ちると欠けうるので、ComfyUI の履歴で数え直す
    import httpx
    hist = httpx.get(COMFY_URL + "/history?max_items=100000", timeout=30).json()
    by_unit: dict[str, dict] = {}
    for e in hist.values():
        pre = [n["inputs"]["filename_prefix"] for n in e["prompt"][2].values() if "filename_prefix" in n.get("inputs", {})]
        u = by_unit.setdefault(pre[0][4:] if pre else "?", {"success": 0, "interrupted": 0, "other": 0})
        st_ = e["status"]["status_str"]
        msgs = [m[0] for m in e["status"].get("messages", [])]
        u["success" if st_ == "success" else "interrupted" if "execution_interrupted" in msgs else "other"] += 1
    res["comfy_executions_by_unit"] = by_unit
    res["comfy_queue_at_end"] = httpx.get(COMFY_URL + "/queue", timeout=30).json()
    (OUT / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    log("result.json を書いた")


def _walk_states(obj):
    if isinstance(obj, dict):
        if "nodes" in obj and "candidates" in obj:
            yield obj
        for v in obj.values():
            yield from _walk_states(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_states(v)
