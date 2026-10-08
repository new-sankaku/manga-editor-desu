"""P60 のハーネスの画面の口（FastAPI）。
- 状態は Temporal のワークフローの query（state）と describe（走っている活動の再試行の回数・生存の知らせの中身）から読む。
- ComfyUI の段数と途中の絵は、ComfyUI の websocket を受けてここで持つ（Temporal の履歴に載せない）。
- 画面の操作（一時停止・再開・1段の取り消し・作業の取り消し・採用・却下・上限の変更・上流の変更）は signal・update・cancel で送る。
実行: <P60 の python> api_server.py
"""
from __future__ import annotations

import asyncio
import json
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn  # noqa: E402
import websockets  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse, Response  # noqa: E402
from temporalio.client import Client, WorkflowExecutionStatus, WorkflowUpdateFailedError  # noqa: E402
from temporalio.service import RPCError  # noqa: E402

from harness_config import API_PORT, COMFY_PORT, HERE, STORE, TASK_QUEUE, TEMPORAL_ADDR  # noqa: E402

app = FastAPI(title="P60 ハーネスの画面の口")
LIVE: dict = {"executing": None, "progress": {}, "preview": {}, "preview_at": {}, "ws": "未接続"}
_client: Client | None = None
_closed_cache: dict[str, dict] = {}


async def client() -> Client:
    global _client
    if _client is None:
        _client = await Client.connect(TEMPORAL_ADDR)
    return _client


async def comfy_ws() -> None:
    """ComfyUI の websocket。client_id を付けずに送った依頼の進み具合と途中の絵は全員に配られる。"""
    while True:
        try:
            async with websockets.connect(f"ws://127.0.0.1:{COMFY_PORT}/ws?clientId=p60-api", max_size=None) as ws:
                LIVE["ws"] = "接続中"
                async for msg in ws:
                    if isinstance(msg, bytes):
                        kind = struct.unpack(">I", msg[:4])[0]
                        if kind == 1 and LIVE["executing"]:
                            LIVE["preview"][LIVE["executing"]] = msg[8:]
                            LIVE["preview_at"][LIVE["executing"]] = time.time()
                        continue
                    d = json.loads(msg)
                    t, data = d.get("type"), d.get("data", {})
                    if t == "executing":
                        LIVE["executing"] = data.get("prompt_id") if data.get("node") is not None else None
                    elif t == "execution_start":
                        LIVE["executing"] = data.get("prompt_id")
                    elif t == "progress":
                        LIVE["progress"][data.get("prompt_id")] = {"value": data["value"], "max": data["max"],
                                                                    "at": time.time()}
        except Exception as e:  # ComfyUI が止まっている間は繋ぎ直す
            LIVE["ws"] = f"未接続（{type(e).__name__}）"
            await asyncio.sleep(2)


@app.on_event("startup")
async def _start() -> None:
    asyncio.create_task(comfy_ws())


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True}


async def _describe(h) -> dict:
    d = await h.describe()
    pend = []
    for pa in d.raw_description.pending_activities:
        details = None
        if pa.heartbeat_details.payloads:
            try:
                details = json.loads(pa.heartbeat_details.payloads[0].data)
            except Exception:
                details = None
        pend.append({"type": pa.activity_type.name, "attempt": pa.attempt, "state": int(pa.state),
                     "heartbeat": details, "last_failure": pa.last_failure.message or None})
    return {"status": d.status.name if d.status else None, "history_length": d.history_length,
            "type": d.workflow_type, "start": d.start_time.isoformat() if d.start_time else None, "pending": pend}


@app.get("/api/state")
async def state(limit: int = 40) -> dict:
    c = await client()
    rows = []
    async for w in c.list_workflows(f'TaskQueue="{TASK_QUEUE}"', limit=limit):
        rows.append(w)
    out = []
    for w in rows:
        h = c.get_workflow_handle(w.id, run_id=w.run_id)
        key = f"{w.id}/{w.run_id}"
        if key in _closed_cache:
            out.append(_closed_cache[key])
            continue
        try:
            desc = await _describe(h)
            st = await h.query("state")
        except RPCError as e:
            out.append({"id": w.id, "error": str(e)})
            continue
        item = {"id": w.id, "run_id": w.run_id, "type": w.workflow_type, "describe": desc, "state": st}
        if desc["status"] != WorkflowExecutionStatus.RUNNING.name:
            _closed_cache[key] = item
        out.append(item)
    return {"now": time.time(), "items": out, "live": {k: LIVE[k] for k in ("executing", "progress", "ws")},
            "previews": list(LIVE["preview"].keys())}


@app.get("/api/preview/{pid}")
async def preview(pid: str) -> Response:
    b = LIVE["preview"].get(pid)
    if b is None:
        raise HTTPException(404, "途中の絵が無い")
    return Response(b, media_type="image/jpeg")


@app.get("/img/{path:path}")
async def img(path: str) -> FileResponse:
    p = (STORE / path).resolve()
    if STORE.resolve() not in p.parents or not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.post("/api/act")
async def act(body: dict) -> dict:
    """{wf, action, args}。update は検証で弾かれたら 409 と理由を返す。"""
    c = await client()
    h = c.get_workflow_handle(body["wf"])
    a, args = body["action"], body.get("args") or {}
    try:
        if a in ("pause", "resume", "cancel_step"):
            await h.signal(a, *([args.get("mode", "now")] if a == "pause" else []))
        elif a == "upstream":
            await h.signal("upstream_changed", args)
        elif a == "cancel":
            await h.cancel()
        elif a == "set_limits":
            return {"ok": True, "result": await h.execute_update("set_limits", args)}
        elif a in ("approve", "reject", "edit"):
            return {"ok": True, "result": await h.execute_update("review", {"action": a, **args})}
        else:
            raise HTTPException(400, f"知らない操作 {a}")
    except WorkflowUpdateFailedError as e:
        raise HTTPException(409, str(e.cause.message if e.cause else e)) from e
    return {"ok": True}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(HERE / "screen" / "index.html")


@app.get("/screen/{name}")
async def screen_file(name: str) -> FileResponse:
    p = (HERE / "screen" / name).resolve()
    if p.parent != (HERE / "screen").resolve() or not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=API_PORT, log_level="warning")
