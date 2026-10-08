"""P60 の測定を流す。場面ごとに out/part_<名前>.json を書き、collect で out/result.json にまとめる。
実行: <P60 の python> run.py <場面> ...   場面：a b c d i s e collect
前に infra.py start で Temporal・ComfyUI・検出器を立て、ここで作業者と画面の口を立てる。"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx  # noqa: E402
from temporalio.client import Client  # noqa: E402

import infra  # noqa: E402
from harness_activities import CLAUDE_LOG, POSTS_LOG  # noqa: E402
from harness_config import (COMFY_URL, DEFAULT_LIMITS, HEIGHT, OUT, PANELS, REGISTRY_LOG, STORE,  # noqa: E402
                            TASK_QUEUE, TEMPORAL_ADDR, WIDTH)

RUN_TAG = time.strftime("%H%M%S")
_client: Client | None = None


def log(*a) -> None:
    line = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(OUT / "run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


async def client() -> Client:
    global _client
    if _client is None:
        _client = await Client.connect(TEMPORAL_ADDR)
    return _client


def unit_input(uid: str, panel: int, *, mode="guided", review="human", eval_enabled=True, seed=11, idempotent=True,
               **lim) -> dict:
    return {"unit_id": uid, "spec": dict(PANELS[panel - 1]), "limits": {**DEFAULT_LIMITS, **lim}, "mode": mode,
            "review": review, "eval_enabled": eval_enabled, "base_seed": seed, "idempotent": idempotent,
            "width": WIDTH, "height": HEIGHT}


async def start(inp: dict, **extra):
    c = await client()
    inp = {**inp, **extra}
    return await c.start_workflow("WorkUnitWorkflow", inp, id=inp["unit_id"], task_queue=TASK_QUEUE)


async def st(h) -> dict:
    return await h.query("state")


async def wait_for(h, pred, timeout=1800, what=""):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            s = await st(h)
            d = await h.describe()
        except Exception:
            await asyncio.sleep(1)
            continue
        if pred(s, d):
            return s, d
        if d.status.name != "RUNNING":
            raise RuntimeError(f"{h.id} が {d.status.name} で終わった（待っていたのは {what}）")
        await asyncio.sleep(0.5)
    raise TimeoutError(f"{h.id}：{what} を待ちきれなかった")


def running_on(node: str, comfy: str | None = None):
    """その段の活動が走っている（生成なら ComfyUI で実行中）とき。"""
    def p(s, d):
        if s.get("current_node") != node or s["nodes"][node]["status"] != "running":
            return False
        pend = d.raw_description.pending_activities
        if not pend or not pend[0].heartbeat_details.payloads:
            return False
        if comfy is None:
            return True
        hb = json.loads(pend[0].heartbeat_details.payloads[0].data)
        return hb.get("comfy") == comfy
    return p


def awaiting(s, d) -> bool:
    return s.get("status") == "awaiting_review"


async def finished(h) -> tuple[dict, str]:
    try:
        r = await h.result()
    except Exception as e:
        r = {"error": type(e).__name__, "message": str(e)[:200]}
    d = await h.describe()
    return r, d.status.name


# ---------------------------------------------------------------- 数える

def _lines(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def counts_for(units: list[str]) -> dict:
    """作業ごとの /prompt の送信・登録・取り下げ・版・Claude の呼び出し。重複は同じ番号で2回以上。"""
    posts = [r for r in _lines(POSTS_LOG) if r["unit"] in units]
    regs = [r for r in _lines(REGISTRY_LOG) if r["unit"] in units]
    pc = Counter(r["pid"] for r in posts)
    rc = Counter(r["pid"] for r in regs if r["event"] == "registered")
    vc = Counter((r["unit"], r["version"]) for r in regs if r["event"] == "version")
    calls = [r for r in _lines(CLAUDE_LOG) if any(r["workflow_id"] == u for u in units)]
    return {"prompt_posts": len(posts), "duplicate_posts": sum(v - 1 for v in pc.values() if v > 1),
            "registrations": sum(rc.values()), "duplicate_registrations": sum(v - 1 for v in rc.values() if v > 1),
            "withdrawn": sum(1 for r in regs if r["event"] == "withdrawn"),
            "already_registered_skips": sum(1 for r in regs if r["event"] == "already"),
            "versions": sum(vc.values()), "duplicate_versions": sum(v - 1 for v in vc.values() if v > 1),
            "claude_calls": len(calls), "claude_killed": sum(1 for r in calls if r.get("killed")),
            "claude_usd": round(sum(r.get("cost", 0) for r in calls), 4)}


async def comfy_queue() -> dict:
    async with httpx.AsyncClient(base_url=COMFY_URL, timeout=10) as c:
        q = (await c.get("/queue")).json()
    return {"running": [x[1] for x in q["queue_running"]], "pending": [x[1] for x in q["queue_pending"]]}


async def orphans(active_pids: set[str] = frozenset()) -> dict:
    """ComfyUI の待ち・実行中に残る依頼のうち、走っている作業のどれも待っていない物。
    置き場の絵のうち、どのワークフローの候補にも無く取り下げもされていない物。"""
    q = await comfy_queue()
    orphan_q = [p for p in q["running"] + q["pending"] if p not in active_pids]
    return {"comfy_orphans": len(orphan_q), "comfy_queue": q}


def store_orphans(units: list[str], states: dict[str, dict]) -> int:
    known = {c["image"] for s in states.values() for c in s["candidates"]}
    regs = [r for r in _lines(REGISTRY_LOG) if r["unit"] in units and r["event"] == "registered"]
    withdrawn = {r["pid"] for r in _lines(REGISTRY_LOG) if r["unit"] in units and r["event"] == "withdrawn"}
    return sum(1 for r in regs if f"{r['pid']}.png" not in known and r["pid"] not in withdrawn
               and (STORE / f"{r['pid']}.png").exists())


def save_part(name: str, data: dict) -> None:
    (OUT / f"part_{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str))
    log("書いた", f"part_{name}.json")


def brief(s: dict) -> dict:
    return {"status": s["status"], "stop_reason": s["stop_reason"], "attempt": s["attempt"], "round": s["round"],
            "budget": s["budget"], "resets": s["resets"],
            "candidates": [{"id": c["id"], "source": c["source"], "seed": c["seed"], "mode": c.get("mode"),
                            "check": None if not c.get("check") else {"passed": c["check"]["passed"],
                                                                      "persons": c["check"]["persons"],
                                                                      "touch": c["check"]["touch"]},
                            "eval": None if not c.get("eval") else {"scores": c["eval"]["scores"],
                                                                    "median": c["eval"]["median"]},
                            "stale": c.get("stale"), "image": c["image"], "gen_seconds": c.get("gen_seconds")}
                           for c in s["candidates"]],
            "nodes": {k: {"count": v["count"], "total_s": v["total_s"]} for k, v in s["nodes"].items()},
            "disagreements": s.get("disagreements")}


# ---------------------------------------------------------------- (a) 検査の結果を使う作り直し と seed だけの作り直し

async def scenario_a() -> None:
    seeds = [11, 22, 33, 44]
    panels = [1, 2]
    hs = []
    for p in panels:
        for sd in seeds:
            for mode in ("guided", "blind"):
                uid = f"a-{RUN_TAG}-p{p}-s{sd}-{mode}"
                hs.append(await start(unit_input(uid, p, mode=mode, review="none", eval_enabled=False, seed=sd,
                                                 max_attempts=3, candidates_per_attempt=1)))
    log("(a)", len(hs), "件を始めた")
    rows = []
    for h in hs:
        r, status = await finished(h)
        s = await st(h)
        rows.append({"unit": h.id, "status": status, "result": r, **brief(s), "adjust": s["adjust"]})
        log("(a)", h.id, r.get("reason"), [c["check"]["passed"] for c in s["candidates"] if c.get("check")])
    summary = {}
    for mode in ("guided", "blind"):
        rs = [x for x in rows if x["unit"].endswith(mode)]
        att = [[c["check"]["passed"] for c in x["candidates"] if c["check"]] for x in rs]
        summary[mode] = {
            "units": len(rs),
            "first_attempt_fail": sum(1 for a in att if a and not a[0]),
            "regenerations": sum(max(0, len(a) - 1) for a in att),
            "regeneration_fail": sum(1 for a in att for v in a[1:] if not v),
            "regeneration_pass": sum(1 for a in att for v in a[1:] if v),
            "passed_within_3": sum(1 for a in att if any(a)),
            "by_panel": {p: {"passed_within_3": sum(1 for x, a in zip(rs, att) if f"-p{p}-" in x["unit"] and any(a)),
                             "units": sum(1 for x in rs if f"-p{p}-" in x["unit"])} for p in panels},
        }
    save_part("a", {"summary": summary, "rows": rows, "counts": counts_for([x["unit"] for x in rows])})


# ---------------------------------------------------------------- 画面の口と作業者

def ensure_worker_and_api() -> None:
    if not (infra.PIDS / "worker").exists():
        infra.start_worker()
    if not (infra.PIDS / "api").exists():
        infra.start_api()


async def main(names: list[str]) -> None:
    OUT.mkdir(exist_ok=True)
    ensure_worker_and_api()
    import scenarios  # 場面 b〜s は別のファイル
    for n in names:
        log("=== 場面", n)
        try:
            if n == "a":
                await scenario_a()
            elif n == "collect":
                scenarios.collect()
            else:
                await getattr(scenarios, f"scenario_{n}")()
        except Exception as e:
            import traceback
            log("場面", n, "が止まった", type(e).__name__, str(e)[:300])
            (OUT / f"error_{n}.txt").write_text(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
