"""comfyui_sender.py の分かれ道を、偽の ComfyUI（httpx.MockTransport）で全部通す。
本物の ComfyUI に送る試験は tests/integration/test_comfyui_real.py。"""

import asyncio
import json
from functools import partial

import httpx
import pytest

from v3server.canonical_tables.service_and_job_tables import Service, ServiceProcess
from v3server.service_senders import comfyui_sender
from v3server.service_senders.comfyui_sender import call_comfyui, check_choices
from v3server.service_senders.sender_result_types import AdapterError

PID = "pid-1"
PNG = b"\x89PNG-fake"
WORKFLOW = {
    "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "a.safetensors", "weight_dtype": "default"}},
    "7": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": 1, "sampler_name": "euler"}},
}
OBJECT_INFO = {
    "UNETLoader": {"input": {"required": {"unet_name": [["a.safetensors"]], "weight_dtype": [["default", "fp8"]]}}},
    "KSampler": {"input": {"required": {"model": ["MODEL"], "seed": ["INT"], "sampler_name": ["COMBO", {"options": ["euler"]}]}}},
}
HISTORY_OK = {"status": {"status_str": "success", "messages": []},
              "outputs": {"9": {"images": [{"filename": "x.png", "subfolder": "", "type": "output"}]}}}


class FakeComfy:
    """偽の ComfyUI。振る舞いは属性で決め、来た要求を calls に残す。"""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.prompt_response = lambda: httpx.Response(200, json={"prompt_id": PID})
        self.histories = [HISTORY_OK]  # 呼ばれるたびに1つ進む（最後は繰り返す）。{} は「まだ無い」
        self.history_response = None  # 指定すると histories より優先
        self.queue = {"queue_running": [], "queue_pending": []}
        self.view = lambda: httpx.Response(200, content=PNG)
        self.object_info = OBJECT_INFO
        self.hist_n = 0
        self.interrupt_fails = False
        self.upload = lambda req: httpx.Response(404)
        self.last_prompt = None

    def __call__(self, req: httpx.Request) -> httpx.Response:
        path = req.url.path
        self.calls.append((req.method, path))
        if path == "/prompt":
            self.last_prompt = json.loads(req.content)["prompt"]
            return self.prompt_response()
        if path == "/upload/image":
            return self.upload(req)
        if path.startswith("/history/"):
            if self.history_response is not None:
                return self.history_response()
            h = self.histories[min(self.hist_n, len(self.histories) - 1)]
            self.hist_n += 1
            return httpx.Response(200, json={PID: h} if h else {})
        if path == "/queue" and req.method == "GET":
            return httpx.Response(200, json=self.queue)
        if path == "/queue":
            self.deleted = json.loads(req.content)["delete"]
            return httpx.Response(200)
        if path == "/interrupt":
            if self.interrupt_fails:
                raise httpx.ConnectError("down")
            return httpx.Response(200)
        if path == "/view":
            return self.view()
        if path.startswith("/object_info/"):
            name = path.rsplit("/", 1)[1]
            return httpx.Response(200, json={name: self.object_info[name]} if name in self.object_info else {})
        return httpx.Response(404)

    def called(self, method: str, path: str) -> bool:
        return (method, path) in self.calls


@pytest.fixture
def comfy(monkeypatch):
    fake = FakeComfy()
    monkeypatch.setattr(comfyui_sender, "POLL_SECONDS", 0.01)
    monkeypatch.setattr(comfyui_sender.httpx, "AsyncClient", partial(httpx.AsyncClient, transport=httpx.MockTransport(fake)))
    return fake


def sp(**kw):
    base = dict(process="draw", comfy_workflow=WORKFLOW, comfy_wait_seconds=5, comfy_check_choices=False)
    return ServiceProcess(**{**base, **kw})


SERVICE = Service(name="comfy", kind="image", location="local", adapter="comfyui", endpoint="http://comfy",
                  send_mode="serial", max_concurrency=1)
REQUEST = {"register": {"role": "panel_art"}}


async def failure(comfy_sp=None, request=None, service=SERVICE) -> AdapterError:
    with pytest.raises(AdapterError) as e:
        await call_comfyui(service, comfy_sp or sp(), REQUEST if request is None else request)
    return e.value


async def test_success_fetches_files(comfy):
    r = await call_comfyui(SERVICE, sp(), REQUEST)
    assert r.output["prompt_id"] == PID
    assert r.output["images"][0]["filename"] == "x.png"
    assert r.image_files == [PNG]
    assert not comfy.called("POST", "/interrupt")


async def test_overrides_applied_and_unknown_node_refused(comfy):
    await call_comfyui(SERVICE, sp(), {**REQUEST, "overrides": {"7": {"seed": 9}}})
    e = await failure(request={**REQUEST, "overrides": {"99": {"seed": 1}}})
    assert e.kind == "refused" and "99" in e.detail


@pytest.mark.parametrize("name, kw", [
    ("住所", {"service": Service(name="c", kind="image", location="local", adapter="comfyui", endpoint=None,
                                send_mode="serial")}),
    ("手順", {"comfy_sp": sp(comfy_workflow=None)}),
    ("待ちの上限", {"comfy_sp": sp(comfy_wait_seconds=None)}),
    ("登録の役目", {"request": {}}),
    ("登録の役目が空", {"request": {"register": {}}}),
])
async def test_request_not_ready_is_refused_before_sending(comfy, name, kw):
    assert (await failure(**kw)).kind == "refused"
    assert comfy.calls == []


async def test_prompt_400_refused_with_node_errors(comfy):
    comfy.prompt_response = lambda: httpx.Response(400, json={
        "error": {"type": "prompt_outputs_failed_validation", "message": "Prompt outputs failed validation"},
        "node_errors": {"7": {"class_type": "KSampler", "errors": [
            {"type": "value_not_in_list", "message": "Value not in list", "details": "sampler_name: 'x'"}]}}})
    e = await failure()
    assert e.kind == "refused"
    assert e.detail.startswith("400 prompt_outputs_failed_validation")
    assert "ノード 7 (KSampler): value_not_in_list" in e.detail


async def test_prompt_missing_node_type_refused(comfy):
    comfy.prompt_response = lambda: httpx.Response(400, json={
        "error": {"type": "missing_node_type", "message": "Node 'X' not found", "details": "Node ID '#7'"},
        "node_errors": {}})
    e = await failure()
    assert e.kind == "refused" and "missing_node_type" in e.detail and "#7" in e.detail


async def test_prompt_429_is_rate_limited_with_retry_after(comfy):
    comfy.prompt_response = lambda: httpx.Response(429, headers={"Retry-After": "7"}, text="slow down")
    e = await failure()
    assert (e.kind, e.retry_after) == ("rate_limited", 7.0)


@pytest.mark.parametrize("code", [500, 502, 503])
async def test_prompt_5xx_is_transport(comfy, code):
    comfy.prompt_response = lambda: httpx.Response(code, text="boom")
    assert (await failure()).kind == "transport"


async def test_prompt_other_4xx_is_refused_even_if_not_json(comfy):
    comfy.prompt_response = lambda: httpx.Response(404, text="not here")
    e = await failure()
    assert e.kind == "refused" and "404" in e.detail


async def test_prompt_broken_bodies(comfy):
    comfy.prompt_response = lambda: httpx.Response(200, text="<html>login</html>")
    assert (await failure()).kind == "broken_response"
    comfy.prompt_response = lambda: httpx.Response(200, json={"ok": True})
    assert (await failure()).kind == "broken_response"
    comfy.prompt_response = lambda: httpx.Response(200, json=[1])
    assert (await failure()).kind == "broken_response"


async def test_connection_failure_is_transport(comfy):
    def boom():
        raise httpx.ConnectError("refused")
    comfy.prompt_response = boom
    assert (await failure()).kind == "transport"


async def test_timeout_is_transport(comfy):
    def slow():
        raise httpx.ReadTimeout("slow")
    comfy.prompt_response = slow
    assert (await failure()).kind == "transport"


async def test_history_not_a_dict_is_broken_response(comfy):
    comfy.history_response = lambda: httpx.Response(200, json=["x"])
    assert (await failure()).kind == "broken_response"
    comfy.history_response = lambda: httpx.Response(200, text="<html>")
    assert (await failure()).kind == "broken_response"
    comfy.history_response = lambda: httpx.Response(200, json={PID: ["not", "a", "dict"]})
    assert (await failure()).kind == "broken_response"


async def test_history_status_codes(comfy):
    comfy.history_response = lambda: httpx.Response(500)
    assert (await failure()).kind == "transport"
    comfy.history_response = lambda: httpx.Response(429, headers={"retry-after": "3"})
    e = await failure()
    assert (e.kind, e.retry_after) == ("rate_limited", 3.0)
    comfy.history_response = lambda: httpx.Response(404)
    assert (await failure()).kind == "broken_response"


async def test_execution_error_is_refused_with_full_exception_message(comfy):
    long = "x" * 900 + "END"
    comfy.histories = [{"status": {"status_str": "error", "messages": [
        ["execution_start", {"prompt_id": PID}],
        ["execution_error", {"node_id": "1", "node_type": "UNETLoader", "exception_message": long}]]}, "outputs": {}}]
    e = await failure()
    assert e.kind == "refused" and "UNETLoader" in e.detail and e.detail.endswith("END")


async def test_execution_interrupted_is_its_own_kind(comfy):
    comfy.histories = [{"status": {"status_str": "error", "messages": [
        ["execution_interrupted", {"node_id": "7", "node_type": "KSampler"}]]}, "outputs": {}}]
    e = await failure()
    assert e.kind == "interrupted" and "KSampler" in e.detail


async def test_error_without_known_message_is_broken_response(comfy):
    comfy.histories = [{"status": {"status_str": "error", "messages": []}, "outputs": {}}]
    assert (await failure()).kind == "broken_response"
    comfy.histories = [{"outputs": {}}]
    assert (await failure()).kind == "broken_response"


async def test_no_images_or_bad_outputs_is_broken_response(comfy):
    comfy.histories = [{"status": {"status_str": "success", "messages": []}, "outputs": {"9": {}}}]
    assert (await failure()).kind == "broken_response"
    comfy.histories = [{"status": {"status_str": "success", "messages": []}, "outputs": []}]
    assert (await failure()).kind == "broken_response"
    comfy.histories = [{"status": {"status_str": "success", "messages": []},
                        "outputs": {"9": {"images": [{"filename": "x.png"}]}}}]
    assert (await failure()).kind == "broken_response"


async def test_view_failure(comfy):
    comfy.view = lambda: httpx.Response(404)
    assert (await failure()).kind == "broken_response"
    comfy.view = lambda: httpx.Response(503)
    assert (await failure()).kind == "transport"


async def test_waits_while_running_then_succeeds(comfy):
    comfy.histories = [{}, {}, HISTORY_OK]
    comfy.queue = {"queue_running": [[0, PID, {}, {}, []]], "queue_pending": []}
    r = await call_comfyui(SERVICE, sp(), REQUEST)
    assert r.image_files == [PNG] and comfy.hist_n == 3


async def test_gone_from_queue_and_history_is_transport(comfy):
    comfy.histories = [{}]
    e = await failure()
    assert e.kind == "transport" and "履歴にも無い" in e.detail


async def test_finished_between_history_and_queue_checks(comfy):
    comfy.histories = [{}, HISTORY_OK]  # 1回目は無く、待ちにも無い→履歴をもう一度見ると出ている
    r = await call_comfyui(SERVICE, sp(), REQUEST)
    assert r.image_files == [PNG]


async def test_wait_limit_exceeded_is_transport(comfy):
    comfy.histories = [{}]
    comfy.queue = {"queue_running": [], "queue_pending": [[1, PID, {}, {}, []]]}
    e = await failure(comfy_sp=sp(comfy_wait_seconds=0))
    assert e.kind == "transport" and "comfy_wait_seconds" in e.detail


async def test_queue_body_broken(comfy):
    comfy.histories = [{}]
    comfy.queue = {"nope": 1}
    assert (await failure()).kind == "broken_response"


# 送る前の選択肢の確認

async def test_check_choices_toggle(comfy):
    bad = {**WORKFLOW, "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "missing.safetensors"}}}
    await call_comfyui(SERVICE, sp(comfy_workflow=bad), REQUEST)  # 切ってあれば確かめず、/prompt に任せる
    assert not any(p.startswith("/object_info") for _, p in comfy.calls)
    e = await failure(comfy_sp=sp(comfy_workflow=bad, comfy_check_choices=True))
    assert e.kind == "refused" and "unet_name" in e.detail and "missing.safetensors" in e.detail
    assert not comfy.called("POST", "/prompt") or comfy.calls.count(("POST", "/prompt")) == 1  # 2回目は送っていない


async def test_check_choices_passes_and_skips_links(comfy):
    r = await call_comfyui(SERVICE, sp(comfy_check_choices=True), REQUEST)
    assert r.image_files == [PNG]


async def test_check_choices_new_combo_format_and_unknown_node(comfy):
    wf = {"7": {"class_type": "KSampler", "inputs": {"sampler_name": "nope"}}}
    e = await failure(comfy_sp=sp(comfy_workflow=wf, comfy_check_choices=True))
    assert e.kind == "refused" and "sampler_name" in e.detail
    wf = {"3": {"class_type": "NoSuchNode", "inputs": {}}}
    e = await failure(comfy_sp=sp(comfy_workflow=wf, comfy_check_choices=True))
    assert e.kind == "refused" and "NoSuchNode" in e.detail


async def test_check_choices_reports_all_problems(comfy):
    wf = {"1": {"class_type": "UNETLoader", "inputs": {"unet_name": "q", "weight_dtype": "z"}}}
    async with httpx.AsyncClient(base_url="http://comfy", transport=httpx.MockTransport(comfy)) as c:
        with pytest.raises(AdapterError) as e:
            await check_choices(c, wf)
    assert "unet_name" in e.value.detail and "weight_dtype" in e.value.detail


# 取り消し

async def cancel_during_wait(comfy, queue):
    comfy.histories = [{}]
    comfy.queue = queue
    task = asyncio.create_task(call_comfyui(SERVICE, sp(), REQUEST))
    for _ in range(100):
        if comfy.called("GET", "/queue"):
            break
        await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_cancel_running_own_prompt_interrupts(comfy):
    await cancel_during_wait(comfy, {"queue_running": [[0, PID, {}, {}, []]], "queue_pending": []})
    assert comfy.called("POST", "/interrupt")
    assert not comfy.called("POST", "/queue")


async def test_cancel_pending_deletes_from_queue_not_interrupt(comfy):
    await cancel_during_wait(comfy, {"queue_running": [[0, "other", {}, {}, []]], "queue_pending": [[1, PID, {}, {}, []]]})
    assert comfy.deleted == [PID]
    assert not comfy.called("POST", "/interrupt")


async def test_cancel_prompt_does_not_interrupt_someone_elses_running_prompt(comfy):
    # 自分の依頼は待ちにも実行中にも無い。他人の実行中の物を止めてはいけない
    comfy.queue = {"queue_running": [[0, "other", {}, {}, []]], "queue_pending": []}
    async with httpx.AsyncClient(base_url="http://comfy", transport=httpx.MockTransport(comfy)) as c:
        assert await comfyui_sender.cancel_prompt(c, PID) == "none"
    assert not comfy.called("POST", "/interrupt") and not comfy.called("POST", "/queue")


async def test_cancel_cleanup_failure_still_raises_cancelled(comfy):
    comfy.interrupt_fails = True
    await cancel_during_wait(comfy, {"queue_running": [[0, PID, {}, {}, []]], "queue_pending": []})
    assert comfy.called("POST", "/interrupt")


# ---------------------------------------------------------------- 元の絵とマスクを上げる（prepared_inputs）


@pytest.fixture
def stored_png(monkeypatch, tmp_path):
    """置き場に絵を1枚置き、その sha256 を返す。"""
    import io as _io

    from PIL import Image

    from v3server.image_file_storage import store_image
    from v3server.server_settings import get_settings
    monkeypatch.setattr(get_settings(), "image_dir", str(tmp_path))
    buf = _io.BytesIO()
    Image.new("L", (8, 8), 0).save(buf, format="PNG")
    return store_image(buf.getvalue()).sha256


def _prepared(sha, node="1", inp="unet_name", purpose="source"):
    return {"node": node, "input": inp, "purpose": purpose, "image_id": "img1", "sha256": sha, "media_type": "image/png"}


async def test_prepared_inputs_are_uploaded_and_put_into_the_workflow(comfy, stored_png):
    sent = {}

    def upload(req):
        sent["body"] = req.content
        return httpx.Response(200, json={"name": f"v3_{stored_png}.png", "subfolder": "sub", "type": "input"})
    comfy.upload = upload
    r = await call_comfyui(SERVICE, sp(), {**REQUEST, "prepared_inputs": [_prepared(stored_png)]})
    assert r.output["uploaded_inputs"] == [{"node": "1", "input": "unet_name", "name": f"sub/v3_{stored_png}.png",
                                            "purpose": "source", "image_id": "img1"}]
    # 上げた名前が手順の入力に入って送られる。上げる前に /prompt は呼ばない
    assert comfy.last_prompt["1"]["inputs"]["unet_name"] == f"sub/v3_{stored_png}.png"
    assert comfy.calls.index(("POST", "/upload/image")) < comfy.calls.index(("POST", "/prompt"))
    assert b'name="overwrite"' in sent["body"] and b'name="type"' in sent["body"]


async def test_upload_failures(comfy, stored_png):
    comfy.upload = lambda req: httpx.Response(500)
    assert (await failure(request={**REQUEST, "prepared_inputs": [_prepared(stored_png)]})).kind == "transport"
    comfy.upload = lambda req: httpx.Response(400, text="bad")
    assert (await failure(request={**REQUEST, "prepared_inputs": [_prepared(stored_png)]})).kind == "refused"
    comfy.upload = lambda req: httpx.Response(200, json={"x": 1})
    assert (await failure(request={**REQUEST, "prepared_inputs": [_prepared(stored_png)]})).kind == "broken_response"
    e = await failure(request={**REQUEST, "prepared_inputs": [_prepared(stored_png, node="99")]})
    assert e.kind == "refused" and "99" in e.detail
    assert not comfy.called("POST", "/prompt")
