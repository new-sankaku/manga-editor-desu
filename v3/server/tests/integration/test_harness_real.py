"""AIハーネスの作画（S4）を、GPU の本物の ComfyUI で1周する。V3_TEST_COMFYUI_GPU_URL が無ければ飛ばす。

ComfyUI だけ本物（SDXL の checkpoint と xinsir の union promax。test_image_generation_gpu.py と同じモデル）。
LLM と検出器は偽物のまま（harness_fakes。本物の絵に対して決めた答えを返す）。Temporal は本物（full の印）。
出来た候補の絵は V3_TEST_GPU_OUT のフォルダに残す（目で見るため）。
"""
import os
import pathlib

import pytest
from conftest import h, wait_for
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
    det_sid = await _service(api, admin, kind="image", adapter="detector", endpoint="http://127.0.0.1:1",
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
