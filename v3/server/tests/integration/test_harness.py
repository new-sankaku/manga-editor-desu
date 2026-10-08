"""AIハーネス（v3server/harness/）を、Temporal・PostgreSQL・OpenFGA を実際に使って通す。

ComfyUI は偽物（harness_fakes.FakeComfyServer。本当に口を開け、/ws で進み具合と途中の絵を送る）。
LLM と検出器も偽物（送り手の差し替え。台本 Script で答えを変える）。本物での1周は test_harness_real.py。
"""


import io
import uuid

import pytest
from conftest import h, new_work, user, wait_for
from harness_fakes import FakeComfyServer, Script, fake_detector, fake_llm
from PIL import Image
from sqlalchemy import func, select
from test_human_ai_interchange import op
from test_image_generation import SD
from test_queue import admin  # noqa: F401  (fixture)

from v3server.canonical_tables.harness_tables import HarnessCandidate, HarnessEvent, HarnessUnit, ServiceCallProgress
from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.service_and_job_tables import Job
from v3server.canonical_tables.work_tree_tables import Panel
from v3server.database_engine import get_sessionmaker
from v3server.harness import live_stream
from v3server.harness.harness_worker_main import HarnessWorker
from v3server.harness.queue_calls import HARNESS_PROCESSES
from v3server.server_settings import get_settings
from v3server.service_senders.sender_by_adapter_name import ADAPTERS

FRAME = {"polygon_mm": [[0, 0], [60, 0], [60, 40], [0, 40]], "bleeds": False}
CONTENT = {"content": "主人公が振り返る", "shot": "胸から上", "angle": "目の高さ",
           "people": [{"name": "アオイ", "face": "中", "facing": "正面"}]}
THRESHOLDS = {"person_score": 0.5, "edge_px": 4, "text_score": 0.5}
DRAWING = {"model_description": "Stable Diffusion 1.5 系。英語のタグをカンマ区切りで受ける",
           "quality_words": "best quality", "style_words": "manga style", "negative_words": "lowres",
           "long_side": 256, "base_params": {"steps": 4, "cfg": 7, "control": "none", "control_strength": 1.0,
                                             "control_end": 1.0, "control_invert": False},
           "redraw_params": {"steps": 4, "cfg": 7, "control": "none", "control_strength": 1.0, "control_end": 1.0,
                             "control_invert": False, "strength": 0.6}}


def limits(**over):
    unit = {"max_attempts": 3, "candidates_per_attempt": 2, "budget_cost": 1000, "budget_seconds": 600,
            "error_stop": 3, "same_failure_restart": 2, "eval_repeats": 1, "disagreement_stop": 2,
            "review_notice_seconds": 600, "resend_limit": 0}
    unit.update(over.pop("unit", {}))
    return {"unit": unit, "max_parallel_units": over.pop("max_parallel_units", 2),
            "completion": over.pop("completion", ["checks_pass", "evaluator_pick", "human_approve"])}


@pytest.fixture(scope="module")
async def comfy():
    server = FakeComfyServer(steps=5, step_seconds=0.1)
    await server.start()
    yield server
    await server.stop()


@pytest.fixture(scope="module", autouse=True)
async def no_leftover_flows(temporal):
    """前の試験の回で残った流れ（データベースは作り直すので、正本の行が無い）を止める。"""
    query = "(WorkflowType='StageWorkflow' OR WorkflowType='WorkUnitWorkflow') AND ExecutionStatus='Running'"
    async for wf in temporal.list_workflows(query):
        await temporal.get_workflow_handle(wf.id, run_id=wf.run_id).terminate("試験の前の後始末")


@pytest.fixture
async def harness(temporal):
    hw = HarnessWorker(temporal)
    await hw.start()
    yield hw
    await hw.shutdown()


@pytest.fixture
def script(monkeypatch):
    s = Script()
    monkeypatch.setitem(ADAPTERS, "litellm", fake_llm(s))
    monkeypatch.setitem(ADAPTERS, "detector", fake_detector(s))
    return s


async def _service(api, admin_user, **body):
    r = await api.post("/services", headers=h(admin_user), json={"name": f"svc-{uuid.uuid4().hex[:6]}",
                                                                 "location": "local", **body})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _route(api, admin_user, sid, process, resend=0, **settings):
    r = await api.put(f"/services/{sid}/processes/{process}", headers=h(admin_user), json=settings)
    assert r.status_code == 200, r.text
    r = await api.put(f"/routes/{process}", headers=h(admin_user), json={
        "service_id": sid, "resend_limit": resend, "regenerate_limit": 0, "ai_task": "drawing", "ai_action": "propose"})
    assert r.status_code == 200, r.text


@pytest.fixture
async def services(api, admin, workers, comfy, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setattr(get_settings(), "image_dir", str(tmp_path))
    comfy_sid = await _service(api, admin, kind="image", adapter="comfyui", endpoint=comfy.url,
                               send_mode="parallel", max_concurrency=4)
    for name in ("text_to_image", "image_to_image"):
        await _route(api, admin, comfy_sid, name, comfy_graph_settings=SD, comfy_wait_seconds=60)
    # litellm は送った先のその先が見えないので api として登録し、作品ごとに送ってよい先へ載せる（make_work）
    llm_sid = await _service(api, admin, kind="text", adapter="litellm", location="api", send_mode="parallel",
                             max_concurrency=4)
    det_sid = await _service(api, admin, kind="image", adapter="detector", endpoint="http://127.0.0.1:1",  # 偽物の検出器は送らない

                             send_mode="parallel", max_concurrency=4)
    for key, process in HARNESS_PROCESSES.items():
        if key.startswith("detect"):
            await _route(api, admin, det_sid, process)
        else:
            await _route(api, admin, llm_sid, process, model="fake", cost_per_call=1)
    await workers.reload()
    API_DESTINATIONS[:] = [llm_sid]
    yield {"comfy": comfy_sid, "llm": llm_sid, "detector": det_sid}
    API_DESTINATIONS.clear()


# 試験の services が登録した api の先。make_work が作品ごとに送ってよい先へ載せる
API_DESTINATIONS: list[str] = []


async def make_work(api, panels=1, thresholds=True, status="verified"):
    a = user()
    ids = await new_work(api, a)
    wid = ids["work"]
    for sid in API_DESTINATIONS:
        r = await op(api, wid, a, {"type": "allow_destination", "service_id": sid, "allowed": True})
        assert r.status_code == 200, r.text
    pids = []
    for i in range(panels):
        pid = uuid.uuid4().hex
        r = await op(api, wid, a, {"type": "add_panel", "id": pid, "page_id": ids["page1"], "order": i + 1,
                                   "frame": FRAME, "content": CONTENT})
        assert r.status_code == 200, r.text
        pids.append(pid)
    r = await op(api, wid, a, {"type": "add_material_entry", "kind": "character", "name": "アオイ",
                               "traits": "短い青い髪", "generation": {"prompt": "1girl, short blue hair"}})
    assert r.status_code == 200, r.text
    if thresholds:
        await set_thresholds(api, wid, a, status)
    return {"a": a, "wid": wid, "pids": pids, "episode": ids["episode"], "page": ids["page1"]}


async def set_thresholds(api, wid, a, status="verified"):
    for k, v in THRESHOLDS.items():
        r = await op(api, wid, a, {"type": "set_threshold", "key": f"harness.drawing.{k}", "value": {"value": v},
                                   "source": "試験", "status": status})
        assert r.status_code == 200, r.text


async def start(api, w, stage="S4", **lim):
    r = await api.post(f"/works/{w['wid']}/harness/stages", headers=h(w["a"]), json={
        "episode_id": w["episode"], "stage": stage, "limits": limits(**lim), "spec": {"drawing": DRAWING}})
    assert r.status_code == 201, r.text
    return r.json()["stage_run_id"]


async def snap(api, w, unit_id=None):
    r = await api.get(f"/works/{w['wid']}/harness/snapshot", headers=h(w["a"]),
                      params={"unit_id": unit_id} if unit_id else {})
    assert r.status_code == 200, r.text
    return r.json()


async def until_unit(api, w, *statuses, timeout=60, index=0):
    async def check():
        units = (await snap(api, w))["units"]
        return units[index] if len(units) > index and units[index]["status"] in statuses else None
    return await wait_for(check, timeout)


async def until_stage(api, w, *statuses, timeout=60):
    async def check():
        runs = (await snap(api, w))["stage_runs"]
        return runs if runs and runs[-1]["status"] in statuses else None
    return await wait_for(check, timeout)


async def unit_post(api, w, uid, what, body):
    return await api.post(f"/works/{w['wid']}/harness/units/{uid}/{what}", headers=h(w["a"]), json=body)


async def jobs_of(uid):
    async with get_sessionmaker()() as session:
        return (await session.execute(select(Job).where(Job.request["harness_key"].as_string().like(f"{uid}%"))
                                      )).scalars().all()


async def discarded(cands) -> list[bool]:
    async with get_sessionmaker()() as session:
        return [(await session.get(ImageFile, c.image_id)).discarded for c in cands if c.image_id]


async def candidates_of(uid):
    async with get_sessionmaker()() as session:
        return (await session.execute(select(HarnessCandidate).where(HarnessCandidate.unit_id == uid)
                                      .order_by(HarnessCandidate.attempt, HarnessCandidate.k_index))).scalars().all()


async def no_duplicate_sends(uid):
    """同じ鍵で生きている依頼は1件だけ。人が今すぐ止めて取り消した依頼は、再開で頼み直すので数えない。"""
    jobs = await jobs_of(uid)
    keys = [j.request["harness_key"] for j in jobs if j.status != "cancelled"]
    assert len(keys) == len(set(keys)), keys
    return jobs


# ---------------------------------------------------------------- 1周


async def test_1周_候補を採って工程を承認すると次の工程へ進む(api, services, harness, script, comfy):
    w = await make_work(api)
    run_id = await start(api, w)
    u = await until_unit(api, w, "awaiting_review")
    assert u["attempt"] == 1 and u["candidates"] == 2
    detail = (await snap(api, w, u["unit_id"]))["unit"]
    steps = [s["step"] for s in detail["steps"]]
    assert steps == ["cut_out", "context", "generate", "check", "evaluate"]
    picked = next(c for c in detail["candidates"] if c["picked"])
    # 手段の無い観点は「判定できない」として必ず出す
    assert any(f["name"] == "背景" and f["ok"] is None for f in picked["check"]["findings"])
    items = (await api.get(f"/works/{w['wid']}/harness/review-items", headers=h(w["a"]),
                           params={"kind": "candidates"})).json()["items"]
    assert [i["unit_id"] for i in items] == [u["unit_id"]]
    # 生成は今の順番待ちを通り、候補ごとに進み具合の鍵を持つ
    jobs = await no_duplicate_sends(u["unit_id"])
    gen = [j for j in jobs if j.process == "text_to_image"]
    assert len(gen) == 2 and all(j.request["progress_key"] for j in gen) and all(j.requested_via == "ai" for j in gen)
    r = await unit_post(api, w, u["unit_id"], "review", {"action": "approve", "candidate_id": picked["id"]})
    assert r.status_code == 200, r.text
    await until_unit(api, w, "done")
    async with get_sessionmaker()() as session:
        panel = await session.get(Panel, w["pids"][0])
        assert panel.image_id == picked["image_id"]
    await until_stage(api, w, "awaiting_review")
    r = await api.post(f"/works/{w['wid']}/harness/stages/{run_id}/approve", headers=h(w["a"]))
    assert r.status_code == 200, r.text
    async def next_stage():
        runs = (await snap(api, w))["stage_runs"]
        return runs if len(runs) == 2 and runs[1]["status"] == "awaiting_review" else None
    runs = await wait_for(next_stage, 60)
    assert [x["stage"] for x in runs] == ["S4", "S5"] and runs[0]["status"] == "done"
    r = await api.post(f"/works/{w['wid']}/harness/stages/{runs[1]['id']}/control", headers=h(w["a"]),
                       json={"action": "cancel"})
    assert r.status_code == 200, r.text
    await until_stage(api, w, "cancelled")


# ---------------------------------------------------------------- 止まる理由


async def _attempt_at_least(api, w, n):
    u = (await snap(api, w))["units"][0]
    return u if u["attempt"] >= n else None


async def test_上限回数で止まり_上限を上げると続き_取り消すと候補を却下にする(api, services, harness, script):
    script.persons = 2  # ネームは1人。確定の閾値なので候補は全部落ちる
    w = await make_work(api)
    await start(api, w, unit={"max_attempts": 2})
    u = await until_unit(api, w, "stopped")
    assert u["attempt"] == 2 and "上限回数" in u["stop_reason"]
    items = (await api.get(f"/works/{w['wid']}/harness/review-items", headers=h(w["a"]))).json()["items"]
    assert {"stopped", "check_failed"} <= {i["kind"] for i in items}
    # 上限は使った分より小さくはできない
    r = await unit_post(api, w, u["unit_id"], "limits", {"limits": {"max_attempts": 1}})
    assert r.status_code == 409 and "小さい" in r.json()["detail"]
    r = await unit_post(api, w, u["unit_id"], "limits", {"limits": {"max_attempts": 3}})
    assert r.status_code == 200, r.text
    await wait_for(lambda: _attempt_at_least(api, w, 3), 60)
    u = await until_unit(api, w, "stopped")
    assert u["attempt"] == 3
    r = await unit_post(api, w, u["unit_id"], "control", {"action": "cancel_unit"})
    assert r.status_code == 200, r.text
    await until_unit(api, w, "cancelled")
    cands = await candidates_of(u["unit_id"])
    assert all(await discarded([c for c in cands if c.attempt == 3]))
    await no_duplicate_sends(u["unit_id"])


async def test_仮の閾値で外れた候補は落とさず指摘だけ(api, services, harness, script):
    script.persons = 2
    w = await make_work(api, status="unverified")
    await start(api, w)
    u = await until_unit(api, w, "awaiting_review")
    cands = await candidates_of(u["unit_id"])
    assert {c.check_verdict for c in cands} == {"flag"}


async def test_評価役の答えが割れたら止まる(api, services, harness, script):
    script.pick = "alternate"
    w = await make_work(api)
    await start(api, w, unit={"eval_repeats": 2, "disagreement_stop": 1})
    u = await until_unit(api, w, "stopped")
    assert "割れた" in u["stop_reason"] and u["attempt"] == 1


async def test_予算に達したら止まる(api, services, harness, script):
    w = await make_work(api)
    await start(api, w, unit={"budget_cost": 1})
    u = await until_unit(api, w, "stopped", "awaiting_review")
    # 1回目の文脈の問いで費用1を使い切る。1回目は最後まで回し、次の回の前に止まる
    if u["status"] == "awaiting_review":
        r = await unit_post(api, w, u["unit_id"], "review", {"action": "reject", "reason": "顔が暗い"})
        assert r.status_code == 200, r.text
        u = await until_unit(api, w, "stopped")
    assert "予算" in u["stop_reason"]


async def test_エラーが続いたら止まる(api, services, harness, script):
    script.tags_broken = True
    w = await make_work(api)
    await start(api, w, unit={"error_stop": 2})
    u = await until_unit(api, w, "stopped")
    assert "エラーが2回続いた" in u["stop_reason"]
    detail = (await snap(api, w, u["unit_id"]))["unit"]
    assert [s["status"] for s in detail["steps"] if s["step"] == "context"] == ["failed", "failed"]


async def test_閾値が無ければ閾値未設定で止まり_置いて再開すると進む(api, services, harness, script):
    w = await make_work(api, thresholds=False)
    await start(api, w)
    u = await until_unit(api, w, "blocked")
    assert "閾値が未設定" in u["stop_reason"] and "harness.drawing.edge_px" in u["stop_reason"]
    await set_thresholds(api, w["wid"], w["a"])
    r = await unit_post(api, w, u["unit_id"], "control", {"action": "resume"})
    assert r.status_code == 200, r.text
    await until_unit(api, w, "awaiting_review")


# ---------------------------------------------------------------- 人の判断


async def test_却下の理由は次の回の問いに入り_却下した回の候補は却下になる(api, services, harness, script):
    w = await make_work(api)
    await start(api, w)
    u = await until_unit(api, w, "awaiting_review")
    r = await unit_post(api, w, u["unit_id"], "review", {"action": "reject"})
    assert r.status_code == 409  # 理由が要る
    r = await unit_post(api, w, u["unit_id"], "review", {"action": "reject", "reason": "表情が硬い"})
    assert r.status_code == 200, r.text
    await wait_for(lambda: _attempt_at_least(api, w, 2), 60)
    u = await until_unit(api, w, "awaiting_review")
    jobs = await jobs_of(u["unit_id"])
    second = next(j for j in jobs if j.request["harness_key"].endswith(":a2:panel_tags"))
    text = second.request["messages"][0]["content"][0]["text"]
    assert "表情が硬い" in text and "1girl, standing, smile" in text
    cands = await candidates_of(u["unit_id"])
    assert all(await discarded([c for c in cands if c.attempt == 1]))
    assert not any(await discarded([c for c in cands if c.attempt == 2]))


async def test_人が直した絵から続けると人の手の範囲を守る処理で作る(api, services, harness, script):
    w = await make_work(api)
    await start(api, w)
    u = await until_unit(api, w, "awaiting_review")
    buf = io.BytesIO()
    Image.new("RGB", (256, 168), (120, 120, 120)).save(buf, format="PNG")
    r = await api.post(f"/works/{w['wid']}/panels/{w['pids'][0]}/image", headers=h(w["a"]),
                       files={"image": ("e.png", buf.getvalue(), "image/png")}, data={"origin": "human_drawn"})
    assert r.status_code in (200, 201), r.text
    edited = r.json()["id"]
    r = await unit_post(api, w, u["unit_id"], "review", {"action": "edit", "image_id": edited})
    assert r.status_code == 200, r.text
    await wait_for(lambda: _attempt_at_least(api, w, 2), 60)
    u = await until_unit(api, w, "awaiting_review")
    jobs = await jobs_of(u["unit_id"])
    redraw = [j for j in jobs if j.process == "image_to_image"]
    assert len(redraw) == 2
    assert all(j.request["protected_mask_input"] == {"node": "protected_mask", "input": "image"} for j in redraw)
    assert all(j.request["input_images"][0]["image_id"] == edited for j in redraw)
    # 直した絵からの戻りの辺は生成へ（文脈は作り直さない）
    detail = (await snap(api, w, u["unit_id"]))["unit"]
    assert [s["step"] for s in detail["steps"] if s["attempt"] == 2] == ["generate", "check", "evaluate"]


# ---------------------------------------------------------------- 一時停止・取り消し・落ちる


async def _until_step(api, w, step, comfy=None):
    async def check():
        u = (await snap(api, w))["units"]
        if not u or u[0]["step"] != step or u[0]["status"] != "running":
            return None
        return u[0] if comfy is None or comfy.running else None
    return await wait_for(check, 60, 0.05)


async def test_今すぐ止めるとComfyUIの実行をprompt_id付きで止め_再開で同じ段からやり直す(
        api, services, harness, script, comfy):
    comfy.step_seconds, comfy.steps = 0.5, 30
    try:
        w = await make_work(api)
        await start(api, w)
        u = await _until_step(api, w, "generate", comfy)
        running = comfy.running
        r = await unit_post(api, w, u["unit_id"], "control", {"action": "pause", "mode": "now"})
        assert r.status_code == 200, r.text
        u = await until_unit(api, w, "paused")
        await until_interrupted(comfy, running)
        assert not comfy.pending  # 送り先に残った物が無い
        comfy.step_seconds, comfy.steps = 0.05, 6
        r = await unit_post(api, w, u["unit_id"], "control", {"action": "resume"})
        assert r.status_code == 200, r.text
        u = await until_unit(api, w, "awaiting_review")
        assert u["attempt"] == 1
        await no_duplicate_sends(u["unit_id"])
    finally:
        comfy.step_seconds, comfy.steps = 0.1, 6


async def until_interrupted(comfy, prompt_id):
    """ComfyUI に prompt_id 付きの /interrupt が届くまで待つ。今の送り手（service_call_activity）は生存を5秒ごとに
    知らせ、取り消しはその返事で届くので、依頼が「取り消し」になってから最大5秒ほど遅れて届く。"""
    async def check():
        return {"prompt_id": prompt_id} in comfy.interrupt_calls and comfy.running != prompt_id
    assert await wait_for(check, 10, 0.1), comfy.interrupt_calls


async def test_段の切れ目で止めると今の段を終えてから止まる(api, services, harness, script):
    script.llm_sleep = 1.0
    w = await make_work(api)
    await start(api, w)
    u = await _until_step(api, w, "context")
    r = await unit_post(api, w, u["unit_id"], "control", {"action": "pause", "mode": "boundary"})
    assert r.status_code == 200, r.text
    u = await until_unit(api, w, "paused")
    detail = (await snap(api, w, u["unit_id"]))["unit"]
    assert [s["status"] for s in detail["steps"] if s["step"] == "context"] == ["done"]
    script.llm_sleep = 0
    await unit_post(api, w, u["unit_id"], "control", {"action": "resume"})
    await until_unit(api, w, "awaiting_review")


async def test_段を取り消すと半端な候補を却下にして次の回へ進む(api, services, harness, script, comfy):
    comfy.step_seconds, comfy.steps = 0.5, 30
    try:
        w = await make_work(api)
        await start(api, w)
        u = await _until_step(api, w, "generate", comfy)
        running = comfy.running
        r = await unit_post(api, w, u["unit_id"], "control", {"action": "cancel_step"})
        assert r.status_code == 200, r.text
        await until_interrupted(comfy, running)
        comfy.step_seconds, comfy.steps = 0.05, 6
        u = await until_unit(api, w, "awaiting_review")
        assert u["attempt"] == 2
        first = [c for c in await candidates_of(u["unit_id"]) if c.attempt == 1]
        assert first and all(c.dropped_reason for c in first)
        assert all(await discarded(first))
    finally:
        comfy.step_seconds, comfy.steps = 0.1, 6


async def test_検査の途中で作業を取り消すと止まり終えてから取り消しになる(api, services, harness, script):
    script.detector_sleep = 1.0
    w = await make_work(api)
    await start(api, w)
    u = await _until_step(api, w, "check")
    r = await unit_post(api, w, u["unit_id"], "control", {"action": "cancel_unit"})
    assert r.status_code == 200, r.text
    await until_unit(api, w, "cancelled")
    jobs = await jobs_of(u["unit_id"])
    assert all(j.status in ("done", "cancelled", "stopped") for j in jobs)
    async with get_sessionmaker()() as session:
        events = (await session.execute(select(HarnessEvent.payload).where(
            HarnessEvent.unit_id == u["unit_id"], HarnessEvent.kind == "unit").order_by(HarnessEvent.id))).scalars().all()
    statuses = [e["status"] for e in events]
    assert statuses.index("cancelling") < statuses.index("cancelled")


async def test_作業者が落ちても送り直しで依頼を重ねず続く(api, services, temporal, script, comfy):
    comfy.step_seconds = 0.4
    hw = HarnessWorker(temporal)
    await hw.start()
    try:
        w = await make_work(api)
        await start(api, w, unit={"resend_limit": 2})
        u = await _until_step(api, w, "generate", comfy)
        await hw.shutdown()  # 作業者が落ちる（依頼は取り消さない）
        comfy.step_seconds = 0.05
        hw = HarnessWorker(temporal)
        await hw.start()
        u = await until_unit(api, w, "awaiting_review", timeout=120)
        jobs = await no_duplicate_sends(u["unit_id"])
        assert len([j for j in jobs if j.process == "text_to_image"]) == 2
        cands = await candidates_of(u["unit_id"])
        assert len(cands) == 2 and all(c.image_id for c in cands)
    finally:
        comfy.step_seconds = 0.1
        await hw.shutdown()


# ---------------------------------------------------------------- 古い印・確認待ち・SSE


async def test_上流が変わると古い印を付け_自動では作り直さず_人が頼むと作り直す(api, services, harness, script):
    w = await make_work(api)
    run_id = await start(api, w, completion=["checks_pass", "evaluator_pick"])
    u = await until_unit(api, w, "done")
    r = await op(api, w["wid"], w["a"], {"type": "update_panel", "id": w["pids"][0],
                                         "content": {**CONTENT, "content": "主人公が走り出す"}})
    assert r.status_code == 200, r.text

    async def stale():
        items = (await api.get(f"/works/{w['wid']}/harness/review-items", headers=h(w["a"]),
                               params={"kind": "stale"})).json()["items"]
        return items or None
    items = await wait_for(stale, 30)
    assert items[0]["effect"] == "redraw" and items[0]["unit_id"] == u["unit_id"]
    assert len((await snap(api, w))["units"]) == 1  # 自動では作り直さない
    r = await api.post(f"/works/{w['wid']}/harness/stages/{run_id}/rerun", headers=h(w["a"]),
                       json={"unit_ids": [u["unit_id"]]})
    assert r.status_code == 200, r.text
    again = await until_unit(api, w, "done", index=1)
    async with get_sessionmaker()() as session:
        assert (await session.get(HarnessUnit, again["unit_id"])).rerun_of == u["unit_id"]
    assert not (await api.get(f"/works/{w['wid']}/harness/review-items", headers=h(w["a"]),
                              params={"kind": "stale"})).json()["items"]


async def test_動いている作業の上流が変わると段の切れ目で止まる(api, services, harness, script):
    script.llm_sleep = 1.5
    w = await make_work(api)
    await start(api, w)
    await _until_step(api, w, "context")
    r = await op(api, w["wid"], w["a"], {"type": "update_panel", "id": w["pids"][0],
                                         "content": {**CONTENT, "shot": "全身"}})
    assert r.status_code == 200, r.text
    u = await until_unit(api, w, "stopped")
    assert "上流が変わった" in u["stop_reason"]
    script.llm_sleep = 0


async def test_同時に回す数を守り_確認待ち一覧を絞り込める(api, services, harness, script):
    w = await make_work(api, panels=3)
    await start(api, w, max_parallel_units=2)
    seen = 0

    async def all_waiting():
        nonlocal seen
        units = (await snap(api, w))["units"]
        busy = [x for x in units if x["status"] not in ("queued", "awaiting_review", "done")]
        seen = max(seen, len(busy))
        return units if len(units) == 3 and all(x["status"] == "awaiting_review" for x in units) else None
    await wait_for(all_waiting, 90, 0.05)
    assert seen <= 2
    items = (await api.get(f"/works/{w['wid']}/harness/review-items", headers=h(w["a"]),
                           params={"kind": "candidates", "page_id": w["page"]})).json()["items"]
    assert len(items) == 3
    r = await api.get(f"/works/{w['wid']}/harness/review-items", headers=h(w["a"]), params={"kind": "nothing"})
    assert r.status_code == 422


async def test_SSEは出来事を順に流し_続きから読み直せ_進み具合と途中の絵も残る(api, services, harness, script, comfy):
    w = await make_work(api)
    await start(api, w)
    await until_unit(api, w, "awaiting_review")
    stop = {"n": 0}

    async def disconnected():
        stop["n"] += 1
        return stop["n"] > 3

    got = [c async for c in live_stream.stream(w["wid"], 0, disconnected)]
    ids = [int(line[4:]) for c in got for line in c.splitlines() if line.startswith("id: ")]
    assert ids == sorted(ids) and len(ids) > 10
    kinds = {line[7:] for c in got for line in c.splitlines() if line.startswith("event: ")}
    assert {"stage", "unit", "step"} <= kinds
    mid = ids[len(ids) // 2]
    stop["n"] = 0
    rest = [c async for c in live_stream.stream(w["wid"], mid, disconnected)]
    rest_ids = [int(line[4:]) for c in rest for line in c.splitlines() if line.startswith("id: ")]
    assert rest_ids == [i for i in ids if i > mid]
    cands = await candidates_of((await snap(api, w))["units"][0]["unit_id"])
    async with get_sessionmaker()() as session:
        rows = [await session.get(ServiceCallProgress, c.id) for c in cands]
    assert all(r.state == "finished" and r.max == comfy.steps and r.preview_b64 for r in rows)


async def test_他人は口を使えない(api, services, harness, script):
    w = await make_work(api)
    other = user()
    r = await api.get(f"/works/{w['wid']}/harness/snapshot", headers=h(other))
    assert r.status_code == 403
    r = await api.post(f"/works/{w['wid']}/harness/stages", headers=h(other), json={
        "episode_id": w["episode"], "stage": "S4", "limits": limits(), "spec": {"drawing": DRAWING}})
    assert r.status_code == 403


async def test_工程を始める前に決めごとと完成条件の誤りを断る(api, services, harness, script):
    w = await make_work(api)
    r = await api.post(f"/works/{w['wid']}/harness/stages", headers=h(w["a"]), json={
        "episode_id": w["episode"], "stage": "S4", "limits": limits(completion=["nothing"]),
        "spec": {"drawing": DRAWING}})
    assert r.status_code == 422
    r = await api.post(f"/works/{w['wid']}/harness/stages", headers=h(w["a"]), json={
        "episode_id": w["episode"], "stage": "S4", "limits": limits(), "spec": {}})
    assert r.status_code == 422 and "spec.drawing" in r.json()["detail"]
    async with get_sessionmaker()() as session:
        n = await session.scalar(select(func.count()).select_from(HarnessUnit).where(HarnessUnit.work_id == w["wid"]))
    assert n == 0


async def test_進み具合はstateの無い書き込みでも落ちない(schema):
    """prompt_id だけ・途中の絵だけの書き込みで NOT NULL に当たって生成が止まったことがある（画面の確かめで見つけた）。"""
    from v3server.service_senders.comfyui_progress import write_progress
    key = uuid.uuid4().hex
    await write_progress(key, prompt_id="p-1")
    await write_progress(key, state="running", value=2, max=5)
    await write_progress(key, preview_media_type="image/png", preview_b64="AA==")
    async with get_sessionmaker()() as session:
        row = await session.get(ServiceCallProgress, key)
        assert (row.prompt_id, row.state, row.value, row.preview_b64) == ("p-1", "running", 2, "AA==")
