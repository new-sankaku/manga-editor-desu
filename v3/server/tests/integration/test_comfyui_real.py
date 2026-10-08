"""本物の ComfyUI に送る試験。V3_TEST_COMFYUI_URL（例 http://127.0.0.1:63188）が無ければ飛ばす。

ComfyUI は CPU でもよい。手順は v3poc/p56_comfy_send/workflow.json（Stable Diffusion 1.5 の unet・text_encoder・vae を
ComfyUI の models に置いた名前）。その名前が入っていなければ飛ばす。絵は 128px・2ステップ（CPU で1枚30秒ほど）。
"""

import asyncio
import io
import json
import os
import pathlib
import time

import httpx
import pytest
from PIL import Image

from v3server.canonical_tables.service_and_job_tables import Service, ServiceProcess
from v3server.service_senders.comfyui_sender import call_comfyui
from v3server.service_senders.sender_result_types import AdapterError

URL = os.environ.get("V3_TEST_COMFYUI_URL")
pytestmark = pytest.mark.skipif(URL is None, reason="V3_TEST_COMFYUI_URL が無い")

WORKFLOW_FILE = pathlib.Path(__file__).parents[4] / "v3poc/p56_comfy_send/workflow.json"
REQUEST = {"register": {"role": "panel_art"}}


def workflow(seed=1, steps=2, size=128) -> dict:
    w = json.loads(WORKFLOW_FILE.read_text())
    w["7"]["inputs"].update(seed=seed, steps=steps)
    w["6"]["inputs"].update(width=size, height=size)
    return w


def service() -> Service:
    return Service(name="comfy-real", kind="image", location="local", adapter="comfyui", endpoint=URL,
                   send_mode="serial", max_concurrency=1)


def process(wf, wait=600, check=True) -> ServiceProcess:
    return ServiceProcess(process="draw", comfy_workflow=wf, comfy_wait_seconds=wait, comfy_check_choices=check)


def pixels(png: bytes) -> bytes:
    return Image.open(io.BytesIO(png)).convert("RGB").tobytes()


@pytest.fixture(scope="module", autouse=True)
async def comfy():
    async with httpx.AsyncClient(base_url=URL, timeout=30) as c:
        try:
            info = (await c.get("/object_info/UNETLoader")).json()["UNETLoader"]["input"]["required"]["unet_name"][0]
        except (httpx.HTTPError, KeyError, ValueError) as e:
            pytest.skip(f"ComfyUI に届かない: {e!r}")
        if "sd15_unet_fp16.safetensors" not in info:
            pytest.skip("試験用のモデル（sd15_*_fp16.safetensors）が ComfyUI に入っていない")
        yield c


@pytest.fixture(autouse=True)
async def clean_queue(comfy):
    yield
    await comfy.post("/queue", json={"clear": True})
    await comfy.post("/interrupt", json={})


async def queue_ids(c):
    q = (await c.get("/queue")).json()
    return [x[1] for x in q["queue_running"]], [x[1] for x in q["queue_pending"]]


async def until(fn, timeout=60):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = await fn()
        if v:
            return v
        await asyncio.sleep(0.3)
    raise AssertionError("時間内に条件を満たさなかった")


async def post_long(c, seed):
    r = await c.post("/prompt", json={"prompt": workflow(seed=seed, steps=60)})
    return r.json()["prompt_id"]


async def test_送って絵を受け取れる_seedを固定すると同じ絵(comfy):
    a = await call_comfyui(service(), process(workflow(seed=5)), REQUEST)
    assert len(a.image_files) == 1 and Image.open(io.BytesIO(a.image_files[0])).size == (128, 128)
    await comfy.post("/free", json={"free_memory": True})  # 結果の再利用を消して、本当に2回計算させる
    b = await call_comfyui(service(), process(workflow(seed=5)), REQUEST)
    assert pixels(a.image_files[0]) == pixels(b.image_files[0])
    c = await call_comfyui(service(), process(workflow(seed=6)), REQUEST)
    assert pixels(c.image_files[0]) != pixels(a.image_files[0])


async def test_壊れた手順はrefused(comfy):
    for mutate in (lambda w: w["7"].update(class_type="NoSuchNode"), lambda w: w["7"]["inputs"].pop("model"),
                   lambda w: w["6"]["inputs"].update(width=0)):
        w = workflow()
        mutate(w)
        with pytest.raises(AdapterError) as e:
            await call_comfyui(service(), process(w, check=False), REQUEST)
        assert e.value.kind == "refused" and e.value.detail.startswith("400 ")


async def test_送る前の確認でモデル名が無いと分かる(comfy):
    w = workflow()
    w["1"]["inputs"]["unet_name"] = "nothing.safetensors"
    with pytest.raises(AdapterError) as e:
        await call_comfyui(service(), process(w, check=True), REQUEST)
    assert e.value.kind == "refused" and "nothing.safetensors" in e.value.detail
    assert await queue_ids(comfy) == ([], [])  # 送っていない


async def test_外から止められるとinterrupted(comfy):
    task = asyncio.create_task(call_comfyui(service(), process(workflow(seed=31, steps=60)), REQUEST))
    await until(lambda: _running(comfy))
    await comfy.post("/interrupt", json={})
    with pytest.raises(AdapterError) as e:
        await task
    assert e.value.kind == "interrupted"


async def _running(c):
    return (await queue_ids(c))[0]


async def test_取り消すと実行中の物を止める(comfy):
    task = asyncio.create_task(call_comfyui(service(), process(workflow(seed=41, steps=60)), REQUEST))
    (pid,) = await until(lambda: _running(comfy))
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    async def finished():
        h = (await comfy.get(f"/history/{pid}")).json()
        return h.get(pid)
    hist = await until(finished, timeout=60)
    assert any(m[0] == "execution_interrupted" for m in hist["status"]["messages"])


async def test_取り消すと順番待ちの物を待ちから消す(comfy):
    await post_long(comfy, 51)  # 実行中の物
    await until(lambda: _running(comfy))
    task = asyncio.create_task(call_comfyui(service(), process(workflow(seed=52, steps=2)), REQUEST))
    pend = await until(lambda: _pending(comfy))
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (await queue_ids(comfy))[1] == [] and pend[0] not in (await queue_ids(comfy))[1]
    assert (await queue_ids(comfy))[0]  # 他の人の実行中の物は止めていない


async def _pending(c):
    return (await queue_ids(c))[1]


async def test_待ちから外から消されるとtransport(comfy):
    await post_long(comfy, 61)
    await until(lambda: _running(comfy))
    task = asyncio.create_task(call_comfyui(service(), process(workflow(seed=62, steps=2)), REQUEST))
    pend = await until(lambda: _pending(comfy))
    await comfy.post("/queue", json={"delete": pend})
    with pytest.raises(AdapterError) as e:
        await asyncio.wait_for(task, 30)
    assert e.value.kind == "transport"
