"""ハーネスの画面を見るための動く見本（Playwright の v3/web/test/harness_ui.mjs が使う）。試験ではない。

本物のサーバー（uvicorn で /web も出す）・Temporal・PostgreSQL・OpenFGA と、今の作業者（WorkerSet）・ハーネスの作業者を
動かす。ComfyUI・LLM・検出器は偽物（harness_fakes.py。どれも偽物だと画面の文書にも書く）。
データベースは .env の V3_DATABASE_URL と同じサーバーの v3_harness_demo（試験の v3_test とは分ける。V3_DEMO_DATABASE_URL で替える）。

  uv run python tests/integration/harness_screen_demo.py --port 8790

操作の口（--port + 1）：
  GET  /info               画面の URL・利用者・作品の id・コマの id
  POST /start              S4（作画）を始める（JSON で上限を上書きできる）
  POST /knob               偽物のつまみ（comfy_steps・comfy_step_seconds・pick・persons・llm_sleep・detector_sleep）
  POST /upstream/{i}       i 番目のコマの中身を変える（上流が変わった印が付く）
  POST /down・/up          API のサーバーを止める・起こす（画面の「切断中」とつなぎ直し）
"""

import argparse
import asyncio
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sqlalchemy.engine import make_url  # noqa: E402

from v3server.server_settings import Settings  # noqa: E402

DB = os.environ.get("V3_DEMO_DATABASE_URL") or make_url(Settings().database_url).set(
    database="v3_harness_demo").render_as_string(hide_password=False)
os.environ["V3_DATABASE_URL"] = DB
os.environ["V3_AUTH_MODE"] = "dev_header"
os.environ["V3_IMAGE_STORE"] = "local"

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from harness_fakes import FakeComfyServer, Script, fake_detector, fake_llm  # noqa: E402
from temporalio.client import Client  # noqa: E402
from test_harness import CONTENT, DRAWING, FRAME, THRESHOLDS, limits  # noqa: E402
from test_image_generation import SD  # noqa: E402

from v3server.database_engine import get_sessionmaker  # noqa: E402
from v3server.generation_queue.queue_worker_main import WorkerSet  # noqa: E402
from v3server.harness.harness_worker_main import HarnessWorker  # noqa: E402
from v3server.harness.queue_calls import HARNESS_PROCESSES  # noqa: E402
from v3server.http_routes.http_app_factory import app  # noqa: E402
from v3server.admin_command_line import grant_admin  # noqa: E402
from v3server.openfga_permissions import open_authz  # noqa: E402
from v3server.server_settings import get_settings  # noqa: E402
from v3server.service_senders.sender_by_adapter_name import ADAPTERS  # noqa: E402

# test_harness が読む conftest は V3_DATABASE_URL を v3_test にするので、見本のデータベースに戻す
os.environ["V3_DATABASE_URL"] = DB
get_settings.cache_clear()

ADMIN = "demo-admin"
AUTHOR = "demo-author"
PANELS = [4, 3]  # ページごとのコマの数


async def serve(a: FastAPI, port: int) -> uvicorn.Server:
    server = uvicorn.Server(uvicorn.Config(a, host="127.0.0.1", port=port, log_level="warning", lifespan="off",
                                           timeout_graceful_shutdown=1))
    server.task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    return server


async def setup(api: httpx.AsyncClient, comfy: FakeComfyServer) -> dict:
    hs = {"X-V3-User": ADMIN}

    async def service(location="local", **body):
        r = await api.post("/services", headers=hs, json={"name": f"demo-{uuid.uuid4().hex[:6]}", "location": location,
                                                          **body})
        r.raise_for_status()
        return r.json()["id"]

    async def route(sid, process, **settings):
        (await api.put(f"/services/{sid}/processes/{process}", headers=hs, json=settings)).raise_for_status()
        (await api.put(f"/routes/{process}", headers=hs, json={"service_id": sid, "resend_limit": 0, "regenerate_limit": 0,
                                                              "ai_task": "drawing", "ai_action": "propose"})).raise_for_status()

    comfy_sid = await service(kind="image", adapter="comfyui", endpoint=comfy.url, send_mode="parallel", max_concurrency=4)
    for name in ("text_to_image", "image_to_image"):
        await route(comfy_sid, name, comfy_graph_settings=SD, comfy_wait_seconds=120)
    # litellm は送った先のその先が見えないので api として登録し、作品の送ってよい先へ載せる（下の ops）
    llm_sid = await service(location="api", kind="text", adapter="litellm", send_mode="parallel", max_concurrency=6)
    # 偽物の検出器は送らない。local と言える住所にする
    det_sid = await service(kind="image", adapter="detector", endpoint="http://127.0.0.1:1", send_mode="parallel",
                            max_concurrency=6)
    for key, process in HARNESS_PROCESSES.items():
        if key.startswith("detect"):
            await route(det_sid, process)
        else:
            await route(llm_sid, process, model="fake", cost_per_call=1)

    a = {"X-V3-User": AUTHOR}
    r = await api.post("/works", headers=a, json={"title": "砂の街（見本）", "reading_direction": "rtl",
                                                  "text_direction": "vertical", "medium": "paper"})
    r.raise_for_status()
    wid = r.json()["id"]
    ids = {"volume": uuid.uuid4().hex, "episode": uuid.uuid4().hex}
    ops = [{"type": "allow_destination", "service_id": llm_sid, "allowed": True},
           {"type": "add_volume", "id": ids["volume"], "number": 1},
           {"type": "add_episode", "id": ids["episode"], "volume_id": ids["volume"], "number": 1}]
    pids = []
    for n, count in enumerate(PANELS, start=1):
        page = uuid.uuid4().hex
        ops.append({"type": "add_page", "id": page, "episode_id": ids["episode"], "number": n})
        for i in range(count):
            pid = uuid.uuid4().hex
            pids.append(pid)
            ops.append({"type": "add_panel", "id": pid, "page_id": page, "order": i + 1, "frame": FRAME,
                        "content": CONTENT})
    ops.append({"type": "add_material_entry", "kind": "character", "name": "アオイ", "traits": "短い青い髪",
                "generation": {"prompt": "1girl, short blue hair"}})
    for k, v in THRESHOLDS.items():
        ops.append({"type": "set_threshold", "key": f"harness.drawing.{k}", "value": {"value": v}, "source": "見本",
                    "status": "verified"})
    for body in ops:
        (await api.post(f"/works/{wid}/ops", headers=a, json=body)).raise_for_status()
    return {"wid": wid, "episode": ids["episode"], "pids": pids, "user": AUTHOR}


def control_app(info: dict, api: httpx.AsyncClient, comfy: FakeComfyServer, script: Script, main: dict) -> FastAPI:
    c = FastAPI()

    @c.post("/down")
    async def down():
        """API のサーバーを止める（画面の SSE が切れる。「切断中」を見るため）。"""
        main["server"].should_exit = True
        await main["server"].task
        return {"ok": True}

    @c.post("/up")
    async def up():
        main["server"] = await serve(app, main["port"])
        return {"ok": True}

    @c.get("/info")
    async def get_info():
        return info

    @c.post("/start")
    async def start(req: Request):
        over = await req.json() if await req.body() else {}
        r = await api.post(f"/works/{info['wid']}/harness/stages", headers={"X-V3-User": AUTHOR}, json={
            "episode_id": info["episode"], "stage": "S4", "limits": limits(**over), "spec": {"drawing": DRAWING}})
        return {"status": r.status_code, "body": r.json()}

    @c.post("/knob")
    async def knob(req: Request):
        body = await req.json()
        if "comfy_steps" in body:
            comfy.steps = body["comfy_steps"]
        if "comfy_step_seconds" in body:
            comfy.step_seconds = body["comfy_step_seconds"]
        for k in ("pick", "persons", "llm_sleep", "detector_sleep", "touch", "texts"):
            if k in body:
                setattr(script, k, body[k])
        return {"ok": True}

    @c.post("/upstream/{i}")
    async def upstream(i: int):
        r = await api.post(f"/works/{info['wid']}/ops", headers={"X-V3-User": AUTHOR}, json={
            "type": "update_panel", "id": info["pids"][i], "content": {**CONTENT, "content": "主人公が砂の上を走り出す"}})
        return {"status": r.status_code}

    return c


async def main(port: int) -> None:
    subprocess.run(["alembic", "upgrade", "head"], check=True, env={**os.environ, "V3_DATABASE_URL": DB})
    get_settings().image_dir = tempfile.mkdtemp(prefix="v3-harness-demo-")
    temporal = await Client.connect(get_settings().temporal_address)
    query = "(WorkflowType='StageWorkflow' OR WorkflowType='WorkUnitWorkflow') AND ExecutionStatus='Running'"
    async for wf in temporal.list_workflows(query):
        await temporal.get_workflow_handle(wf.id, run_id=wf.run_id).terminate("見本の前の後始末")
    async with get_sessionmaker()() as session:
        app.state.authz = await open_authz(session)
    app.state.temporal = temporal
    await grant_admin(ADMIN, revoke=False)

    script = Script()
    script.llm_sleep, script.detector_sleep = 0.6, 0.4
    ADAPTERS["litellm"] = fake_llm(script)
    ADAPTERS["detector"] = fake_detector(script)
    comfy = FakeComfyServer(steps=10, step_seconds=0.35)
    await comfy.start()
    workers = WorkerSet(temporal)
    await workers.start()
    harness = HarnessWorker(temporal)
    await harness.start()
    main_server = {"server": await serve(app, port), "port": port}
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=30) as api:
        info = await setup(api, comfy)
        await workers.reload()
        info["web"] = f"http://127.0.0.1:{port}/web/harness/?work={info['wid']}"
        await serve(control_app(info, api, comfy, script, main_server), port + 1)
        print("READY", info["web"], flush=True)
        try:
            await asyncio.Event().wait()
        finally:
            await harness.shutdown()
            await workers.shutdown()
            await comfy.stop()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8790)
    asyncio.run(main(p.parse_args().port))
