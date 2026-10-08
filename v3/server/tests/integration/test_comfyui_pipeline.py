"""ComfyUI の絵が、依頼 → 送信 → 受け取り → 置き場 → AI の操作での登録 → job.result まで届くか。
ComfyUI は偽（httpx.MockTransport）。Temporal・PostgreSQL・OpenFGA は実際に使う。"""

import io
import types
import uuid
from functools import partial

import httpx
import pytest
from conftest import h, new_work, user, wait_for
from PIL import Image
from test_queue import ADMIN, admin, enqueue, until_status  # noqa: F401  (admin は fixture)

from v3server.server_settings import get_settings
from v3server.service_senders import comfyui_sender

PID = "pid-pipeline"


def png() -> bytes:
    buf = io.BytesIO()
    Image.new("L", (32, 48), 128).save(buf, format="PNG")
    return buf.getvalue()


class SlowFakeComfy:
    """/history を finish_after 回目から返す。止められた記録を残す。"""

    def __init__(self, finish_after: int | None):
        self.finish_after, self.n, self.calls, self.interrupted = finish_after, 0, [], False

    def __call__(self, req: httpx.Request) -> httpx.Response:
        path = req.url.path
        self.calls.append((req.method, path))
        if path == "/prompt":
            return httpx.Response(200, json={"prompt_id": PID})
        if path.startswith("/history/"):
            self.n += 1
            if self.interrupted:
                return httpx.Response(200, json={PID: {"status": {"status_str": "error", "messages": [
                    ["execution_interrupted", {"node_type": "KSampler"}]]}, "outputs": {}}})
            if self.finish_after is not None and self.n >= self.finish_after:
                return httpx.Response(200, json={PID: {"status": {"status_str": "success", "messages": []}, "outputs": {
                    "9": {"images": [{"filename": "a.png", "subfolder": "", "type": "output"}]}}}})
            return httpx.Response(200, json={})
        if path == "/queue" and req.method == "GET":
            return httpx.Response(200, json={"queue_running": [[0, PID, {}, {}, []]], "queue_pending": []})
        if path == "/interrupt":
            self.interrupted = True
            return httpx.Response(200)
        if path == "/view":
            return httpx.Response(200, content=png())
        return httpx.Response(404)


@pytest.fixture
def fake_comfy(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "image_dir", str(tmp_path))
    monkeypatch.setattr(comfyui_sender, "POLL_SECONDS", 0.1)

    def install(fake):
        # 送り手の中の httpx だけを差し替える（httpx 本体を差し替えると、OpenFGA への通信も偽になる）
        shim = types.SimpleNamespace(**{k: getattr(httpx, k) for k in dir(httpx) if not k.startswith("_")})
        shim.AsyncClient = partial(httpx.AsyncClient, transport=httpx.MockTransport(fake))
        monkeypatch.setattr(comfyui_sender, "httpx", shim)
        return fake
    return install


async def make_comfy_service(api, admin_user):
    name, process = f"comfy-{uuid.uuid4().hex[:6]}", f"draw-{uuid.uuid4().hex[:6]}"
    r = await api.post("/services", headers=h(admin_user), json={
        "name": name, "kind": "image", "location": "local", "adapter": "comfyui", "endpoint": "http://comfy",
        "send_mode": "serial"})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    r = await api.put(f"/services/{sid}/processes/{process}", headers=h(admin_user), json={
        "comfy_workflow": {"9": {"class_type": "SaveImage", "inputs": {}}}, "comfy_wait_seconds": 30})
    assert r.status_code == 200, r.text
    assert r.json()["comfy_wait_seconds"] == 30
    r = await api.put(f"/routes/{process}", headers=h(admin_user),
                      json={"service_id": sid, "resend_limit": 0, "regenerate_limit": 0, "ai_task": "drawing",
                            "ai_action": "propose"})
    assert r.status_code == 200, r.text
    await_reload = process
    return sid, await_reload


async def test_生成した絵がAIの操作で登録されjob_resultに入る(api, admin, workers, fake_comfy):
    fake_comfy(SlowFakeComfy(finish_after=2))
    a = user()
    ids = await new_work(api, a)
    wid = ids["work"]
    _, process = await make_comfy_service(api, admin)
    await workers.reload()
    r = await api.post(f"/works/{wid}/jobs", headers=h(a), json={
        "process": process, "page_id": ids["page1"],
        "request": {"register": {"role": "panel_art", "page_id": ids["page1"]}}})
    assert r.status_code == 201, r.text
    j = await until_status(api, wid, a, r.json()["id"], "done", "stopped")
    assert j["status"] == "done", j
    (reg,) = j["result"]["registered"]
    imgs = (await api.get(f"/works/{wid}/images", headers=h(a), params={"page_id": ids["page1"]})).json()
    (img,) = imgs
    assert img["id"] == reg["image_id"] and img["origin"] == "generated" and img["job_id"] == j["id"]
    assert (img["registered_by_kind"], img["width"], img["height"]) == ("ai", 32, 48)
    assert (await api.get(f"/works/{wid}/images/{img['id']}/file", headers=h(a))).content == png()
    # 出来事には、頼んだ人の代理の AI として残る
    events = (await api.get(f"/works/{wid}/events", headers=h(a))).json()
    ev = next(e for e in events if e["op_type"] == "register_image")
    assert (ev["actor_kind"], ev["on_behalf_of"]) == ("ai", a)


async def test_登録を断られたら依頼は止まる(api, admin, workers, fake_comfy):
    fake_comfy(SlowFakeComfy(finish_after=1))
    a = user()
    ids = await new_work(api, a)
    wid = ids["work"]
    _, process = await make_comfy_service(api, admin)
    await workers.reload()
    jid = await enqueue(api, wid, a, process, register={"role": "panel_art", "page_id": uuid.uuid4().hex})
    j = await until_status(api, wid, a, jid, "done", "stopped")
    assert j["status"] == "stopped" and j["failure_kind"] == "refused" and "絵の登録を断られた" in j["failure_detail"]
    assert (await api.get(f"/works/{wid}/images", headers=h(a))).json() == []


async def test_登録の役目が無い依頼は送らずに止まる(api, admin, workers, fake_comfy):
    fake = fake_comfy(SlowFakeComfy(finish_after=1))
    a = user()
    wid = (await new_work(api, a))["work"]
    _, process = await make_comfy_service(api, admin)
    await workers.reload()
    jid = await enqueue(api, wid, a, process)
    j = await until_status(api, wid, a, jid, "stopped")
    assert j["failure_kind"] == "refused" and "register" in j["failure_detail"]
    assert fake.calls == []


async def test_取り消すと送り先の実行中の物も止める(api, admin, workers, fake_comfy):
    fake = fake_comfy(SlowFakeComfy(finish_after=None))
    a = user()
    ids = await new_work(api, a)
    wid = ids["work"]
    _, process = await make_comfy_service(api, admin)
    await workers.reload()
    jid = await enqueue(api, wid, a, process, register={"role": "panel_art"})
    await until_status(api, wid, a, jid, "running")

    async def polled():
        return fake.n >= 2
    await wait_for(polled)
    assert (await api.post(f"/works/{wid}/jobs/{jid}/cancel", headers=h(a))).status_code == 202
    await until_status(api, wid, a, jid, "cancelled", timeout=20)

    async def interrupted():
        return fake.interrupted
    await wait_for(interrupted, timeout=40)  # 取り消しは活動の生存の知らせ（5秒ごと）で届く
