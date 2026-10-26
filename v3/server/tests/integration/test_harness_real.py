"""AIハーネスの作画（S4）を、GPU の本物の ComfyUI で1周する・囲んで直す・今すぐ止める。V3_TEST_COMFYUI_GPU_URL が無ければ飛ばす。

ComfyUI だけ本物（SDXL の checkpoint と xinsir の union promax。test_image_generation_gpu.py と同じモデル）。
LLM と検出器は偽物のまま（harness_fakes。本物の絵に対して決めた答えを返す）。Temporal は本物（full の印）。
V3_TEST_DETECTOR_URL を与えると、検出器も本物にする試験が1件流れる（LLM は偽物のまま）。
出来た候補の絵は V3_TEST_GPU_OUT のフォルダに残す（目で見るため）。
"""
import io
import json
import os
import pathlib

import httpx
import numpy as np
import pytest
from conftest import h, wait_for
from PIL import Image
from test_harness import (  # noqa: F401  (fixture)
    API_DESTINATIONS,
    DRAWING,
    HARNESS_PROCESSES,
    _route,
    _service,
    harness,
    harness_temporal,
    make_work,
    no_duplicate_sends,
    no_leftover_flows,
    script,
    snap,
    start,
    unit_post,
    until_stage,
    until_unit,
)
from test_image_generation_gpu import SDXL, URL, models_present  # noqa: F401  (fixture)
from test_queue import admin  # noqa: F401  (fixture)

from v3server.server_settings import get_settings
from v3server.service_senders.sender_by_adapter_name import ADAPTERS

DET_URL = os.environ.get("V3_TEST_DETECTOR_URL")
REAL_DETECTOR = ADAPTERS["detector"]  # script が偽物に替える前の本物
pytestmark = [pytest.mark.skipif(URL is None, reason="V3_TEST_COMFYUI_GPU_URL が無い"), pytest.mark.full]

PARAMS = {"steps": 25, "cfg": 6, "control": "none", "control_strength": 1.0, "control_end": 1.0,
          "control_invert": False}
REAL_DRAWING = {**DRAWING, "model_description": "SDXL（Illustrious 系）。英語のタグをカンマ区切りで受ける",
                "quality_words": "masterpiece, best quality", "long_side": 1024, "base_params": PARAMS,
                "redraw_params": {**PARAMS, "strength": 0.6},
                "fix": {**DRAWING["fix"], "params": {**DRAWING["fix"]["params"], "steps": 25, "cfg": 6}}}


@pytest.fixture
async def services(api, admin, harness_temporal, monkeypatch, tmp_path):  # noqa: F811
    workers = harness_temporal[0]
    monkeypatch.setattr(get_settings(), "image_dir", str(tmp_path))
    comfy_sid = await _service(api, admin, kind="image", adapter="comfyui", endpoint=URL, send_mode="serial",
                               max_concurrency=1)
    for name in ("text_to_image", "image_to_image", "inpaint"):
        await _route(api, admin, comfy_sid, name, comfy_graph_settings=SDXL, comfy_wait_seconds=900)
    llm_sid = await _service(api, admin, kind="text", adapter="litellm", location="api", send_mode="parallel",
                             max_concurrency=4)
    det_sid = await _service(api, admin, kind="image", adapter="detector", endpoint=DET_URL or "http://127.0.0.1:1",
                             send_mode="parallel", max_concurrency=4)
    for key, process in HARNESS_PROCESSES.items():
        if key.startswith("detect"):
            await _route(api, admin, det_sid, process)
        else:
            await _route(api, admin, llm_sid, process, model="fake", cost_per_call=1)
    await workers.reload()
    API_DESTINATIONS[:] = [llm_sid]
    yield {"comfy": comfy_sid}
    API_DESTINATIONS.clear()


async def test_本物のComfyUIで作画を1周し_採った絵がコマに載る(api, services, harness, script, tmp_path):
    w = await make_work(api)
    run_id = await start(api, w, drawing=REAL_DRAWING, unit={"budget_seconds": 1800, "wait_seconds": 900})
    u = await until_unit(api, w, "awaiting_review", "stopped", "failed", timeout=1800)
    assert u["status"] == "awaiting_review", u
    detail = (await snap(api, w, u["unit_id"]))["unit"]
    assert [s["step"] for s in detail["steps"]] == ["cut_out", "context", "generate", "check", "evaluate"]
    jobs = await no_duplicate_sends(u["unit_id"])
    gen = [j for j in jobs if j.process == "text_to_image"]
    assert len(gen) == 2 and all(j.status == "done" for j in gen), [(j.process, j.status) for j in gen]
    out = pathlib.Path(os.environ.get("V3_TEST_GPU_OUT", tmp_path / "out"))
    out.mkdir(parents=True, exist_ok=True)
    for c in detail["candidates"]:
        r = await api.get(f"/works/{w['wid']}/images/{c['image_id']}/file", headers=h(w["a"]))
        assert r.status_code == 200
        (out / f"harness_k{c['k_index']}{'_picked' if c['picked'] else ''}.png").write_bytes(r.content)
    picked = next(c for c in detail["candidates"] if c["picked"])
    r = await unit_post(api, w, u["unit_id"], "review", {"action": "approve", "candidate_id": picked["id"]})
    assert r.status_code == 200, r.text
    await until_unit(api, w, "done", timeout=120)
    await until_stage(api, w, "awaiting_review", timeout=120)
    r = await api.post(f"/works/{w['wid']}/harness/stages/{run_id}/approve", headers=h(w["a"]))
    assert r.status_code == 200, r.text

    async def s5_started():
        s = await snap(api, w)
        return s["stage_runs"] if len(s["stage_runs"]) == 2 else None
    runs = await wait_for(s5_started, 60)
    r = await api.post(f"/works/{w['wid']}/harness/stages/{runs[1]['id']}/control", headers=h(w["a"]),
                       json={"action": "cancel"})
    assert r.status_code == 200, r.text


def _bbox(polygons, margin, size):
    xs = [p[0] for poly in polygons for p in poly]
    ys = [p[1] for poly in polygons for p in poly]
    return (max(0, int(min(xs)) - margin), max(0, int(min(ys)) - margin),
            min(size[0], int(max(xs)) + margin + 1), min(size[1], int(max(ys)) + margin + 1))


async def test_本物のComfyUIで絵の中の文字で落ちた候補を囲んで直し_囲んだ外は変えない(
        api, services, harness, script, tmp_path):
    script.texts, script.texts_calls = 1, 2  # 2枚の初めの検査だけ文字が出る（直した後は消えた）
    w = await make_work(api)
    await start(api, w, drawing=REAL_DRAWING, unit={"budget_seconds": 1800, "wait_seconds": 900})
    u = await until_unit(api, w, "awaiting_review", "stopped", "failed", timeout=1800)
    assert u["status"] == "awaiting_review", u
    d = (await snap(api, w, u["unit_id"]))["unit"]
    assert [s["step"] for s in d["steps"]] == ["cut_out", "context", "generate", "check", "fix", "check", "evaluate"]
    jobs = await no_duplicate_sends(u["unit_id"])
    inpaint = [j for j in jobs if j.process == "inpaint"]
    assert len(inpaint) == 2 and all(j.status == "done" for j in inpaint), [(j.process, j.status) for j in jobs]
    fixed = [c for c in d["candidates"] if c["fixed_from"]]
    assert len(fixed) == 2 and not d["fix_fallbacks"]
    by_id = {c["id"]: c for c in d["candidates"]}
    out = pathlib.Path(os.environ.get("V3_TEST_GPU_OUT", tmp_path / "out"))
    out.mkdir(parents=True, exist_ok=True)

    async def pixels(image_id):
        r = await api.get(f"/works/{w['wid']}/images/{image_id}/file", headers=h(w["a"]))
        assert r.status_code == 200
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    for c in fixed:
        before, after = await pixels(by_id[c["fixed_from"]]["image_id"]), await pixels(c["image_id"])
        before.save(out / f"fix_k{c['k_index']}_before.png")
        after.save(out / f"fix_k{c['k_index']}_after.png")
        assert before.size == after.size
        job = next(j for j in inpaint if j.request["input_images"][0]["image_id"] == by_id[c["fixed_from"]]["image_id"])
        box = _bbox(job.request["input_images"][1]["region_px"], 64, before.size)
        diff = np.abs(np.asarray(before, dtype=np.int16) - np.asarray(after, dtype=np.int16)).max(axis=2)
        inside = diff[box[1]:box[3], box[0]:box[2]].copy()
        diff[box[1]:box[3], box[0]:box[2]] = 0
        assert int(diff.max()) == 0, f"囲んだ外が変わった（最大の差 {int(diff.max())}、範囲 {box}）"
        assert int(inside.max()) > 0, "囲んだ所が変わっていない"


async def _comfy_running():
    async with httpx.AsyncClient(timeout=10) as c:
        q = (await c.get(f"{URL}/queue")).json()
    return [x[1] for x in q["queue_running"]], [x[1] for x in q["queue_pending"]]


async def test_本物のComfyUIで今すぐ止めると実行が止まり_再開で同じ回のまま候補が出る(
        api, services, harness, script):
    w = await make_work(api)
    await start(api, w, drawing=REAL_DRAWING, unit={"budget_seconds": 1800, "wait_seconds": 900})

    async def generating():
        units = (await snap(api, w))["units"]
        running, _ = await _comfy_running()
        return units[0] if units and units[0]["step"] == "generate" and running else None
    u = await wait_for(generating, 600, 0.2)
    first, _ = await _comfy_running()
    r = await unit_post(api, w, u["unit_id"], "control", {"action": "pause", "mode": "now"})
    assert r.status_code == 200, r.text
    await until_unit(api, w, "paused", timeout=60)

    async def stopped():
        running, pending = await _comfy_running()
        return True if first[0] not in running and not pending else None
    assert await wait_for(stopped, 30, 0.2), await _comfy_running()
    async with httpx.AsyncClient(timeout=10) as c:
        hist = (await c.get(f"{URL}/history/{first[0]}")).json()
    msgs = [m[0] for m in hist.get(first[0], {}).get("status", {}).get("messages", [])]
    assert "execution_interrupted" in msgs, msgs
    r = await unit_post(api, w, u["unit_id"], "control", {"action": "resume"})
    assert r.status_code == 200, r.text
    u = await until_unit(api, w, "awaiting_review", "stopped", "failed", timeout=1800)
    assert u["status"] == "awaiting_review" and u["attempt"] == 1, u
    await no_duplicate_sends(u["unit_id"])


@pytest.mark.skipif(DET_URL is None, reason="V3_TEST_DETECTOR_URL が無い")
async def test_本物のComfyUIと検出器で作画を回し_検査の結果が候補に残る(
        api, services, harness, script, monkeypatch, tmp_path):
    monkeypatch.setitem(ADAPTERS, "detector", REAL_DETECTOR)
    w = await make_work(api)
    await start(api, w, drawing=REAL_DRAWING, unit={"budget_seconds": 1800, "wait_seconds": 900, "max_attempts": 2})
    u = await until_unit(api, w, "awaiting_review", "stopped", "failed", timeout=2400)
    detail = (await snap(api, w, u["unit_id"]))["unit"]
    out = pathlib.Path(os.environ.get("V3_TEST_GPU_OUT", tmp_path / "out"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "harness_real_detector.json").write_text(json.dumps(
        {"unit": u, "candidates": [{k: c[k] for k in ("id", "k_index", "picked", "check_verdict", "check")}
                                   for c in detail["candidates"]]}, ensure_ascii=False, indent=1), encoding="utf-8")
    assert u["status"] in ("awaiting_review", "stopped"), u
    jobs = await no_duplicate_sends(u["unit_id"])
    det = [j for j in jobs if j.process.startswith("harness_detect")]
    assert det and all(j.status == "done" for j in det), [(j.process, j.status) for j in det]
    assert {j.process for j in det} >= {"harness_detect_person", "harness_detect_text", "harness_detect_hands",
                                         "harness_detect_age"}
    assert detail["candidates"] and all(c["check"]["findings"] for c in detail["candidates"])
