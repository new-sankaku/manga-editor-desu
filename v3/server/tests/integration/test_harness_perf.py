"""ハーネスの量と遅れを測る（perf。ふだんの試験からは外す。V3_PERF=1 で流す。-s を付けると数が出る）。

- 今すぐ止める遅れ：人が「今すぐ止める」を押してから、偽の ComfyUI に prompt_id 付きの /interrupt が届くまで。
  生存の知らせの間隔（ハーネスの段と送り手の2か所）を、直す前（2秒・5秒）と直した後（今の値）で比べる
- 量：コマ 100 の作画の工程を、人の判断なしで（検査・評価役で終わる）流し切る。全部が終わるまでの時間・
  今の状態（snapshot）を取る時間・同じ依頼を重ねていないかを見る
"""

import os
import statistics
import time

import pytest
from conftest import h, wait_for
from test_harness import (  # noqa: F401  (fixture)
    admin,
    comfy,
    harness,
    harness_temporal,
    make_work,
    no_duplicate_sends,
    no_leftover_flows,
    script,
    services,
    snap,
    start,
    unit_post,
    until_stage,
    until_unit,
)

from v3server.generation_queue import service_call_activity
from v3server.harness import harness_activities

pytestmark = [pytest.mark.perf,
              pytest.mark.skipif(os.environ.get("V3_PERF") != "1", reason="時間を測る試験。V3_PERF=1 で流す")]

REPEATS = 3


async def _pause_delay(api, comfy) -> float:
    w = await make_work(api)
    await start(api, w)

    async def generating():
        units = (await snap(api, w))["units"]
        return units[0] if units and units[0]["step"] == "generate" and comfy.running else None
    u = await wait_for(generating, 60, 0.02)
    running = comfy.running
    t0 = time.monotonic()
    r = await unit_post(api, w, u["unit_id"], "control", {"action": "pause", "mode": "now"})
    assert r.status_code == 200, r.text

    async def interrupted():
        return {"prompt_id": running} in comfy.interrupt_calls
    await wait_for(interrupted, 30, 0.02)
    delay = time.monotonic() - t0
    await until_unit(api, w, "paused")
    r = await unit_post(api, w, u["unit_id"], "control", {"action": "cancel_unit"})
    assert r.status_code == 200, r.text
    await until_unit(api, w, "cancelled")
    return delay


@pytest.mark.parametrize(("label", "harness_beat", "sender_beat"), [
    ("直す前", 2, 5),
    ("直した後", harness_activities.HEARTBEAT_SECONDS, service_call_activity.HEARTBEAT_SECONDS),
])
async def test_今すぐ止める遅れ(api, services, harness, script, comfy, monkeypatch, label, harness_beat, sender_beat):
    monkeypatch.setattr(harness_activities, "HEARTBEAT_SECONDS", harness_beat)
    monkeypatch.setattr(service_call_activity, "HEARTBEAT_SECONDS", sender_beat)
    comfy.step_seconds, comfy.steps = 0.5, 40
    try:
        delays = [await _pause_delay(api, comfy) for _ in range(REPEATS)]
    finally:
        comfy.step_seconds, comfy.steps = 0.1, 6
    print(f"\n今すぐ止める遅れ {label}（段 {harness_beat} 秒・送り手 {sender_beat} 秒）: "
          f"{', '.join(f'{d:.2f}' for d in delays)} 秒（中央 {statistics.median(delays):.2f}）")
    # 生存の知らせ2つ分（段と送り手）と、取り消しを順番待ちへ渡す見回り（queue_calls.POLL_SECONDS）より遅れない
    assert max(delays) < harness_beat + sender_beat + 2


async def test_コマ100の作画を流し切る(api, services, harness, script, comfy):
    comfy.step_seconds, comfy.steps = 0.005, 2
    try:
        w = await make_work(api, panels=100)
        t0 = time.monotonic()
        await start(api, w, max_parallel_units=10, completion=["checks_pass", "evaluator_pick"])

        async def all_done():
            units = (await snap(api, w))["units"]
            return units if len(units) == 100 and all(u["status"] == "done" for u in units) else None
        units = await wait_for(all_done, 900, 1)
        total = time.monotonic() - t0
        await until_stage(api, w, "awaiting_review", timeout=120)
        snaps = []
        for _ in range(5):
            s0 = time.monotonic()
            r = await api.get(f"/works/{w['wid']}/harness/snapshot", headers=h(w["a"]))
            assert r.status_code == 200
            snaps.append(time.monotonic() - s0)
        for u in units:
            await no_duplicate_sends(u["unit_id"])
        attempts = [u["attempt"] for u in units]
        print(f"\nコマ100: 全部が終わるまで {total:.1f} 秒（1作業あたり {total / 100:.2f} 秒・同時に10）。"
              f"回の数 平均 {statistics.mean(attempts):.2f}・最大 {max(attempts)}。"
              f"snapshot {statistics.median(snaps) * 1000:.0f} ms（中央）")
    finally:
        comfy.step_seconds, comfy.steps = 0.1, 6
