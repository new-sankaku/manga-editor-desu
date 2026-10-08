"""【模型】ComfyUI の代わり（P60 の b〜s を流すため。絵の中身は本物ではない）。
この環境の CPU では1枚に1〜3分かかり、b〜s の場面を流しきれなかったので、口だけ ComfyUI 0.39.2 と同じにした物を使う。
- 口：/system_stats・/prompt（prompt_id を受ける。同じ番号の重複を調べないのも本物と同じ）・/queue（見る・消す）・
  /interrupt（prompt_id 付き）・/history・/upload/image・/view・/ws（executing・progress・途中の絵）
- 1件ずつ実行する。1段あたり P60_MOCK_STEP_SEC 秒（既定 1.0）× KSampler の steps。
- 絵：(a) で本物の ComfyUI が作った 320px の絵（comfy_out の p60_a-*）の中から、seed と文の組で決まった1枚を選び、大きさを合わせて返す。
  絵から作り直す時は、守る範囲（protected_mask の白）に元の絵を貼り戻す（本物の作業の流れと同じ扱い）。
  だから検査・評価の結果は「絵の良し悪し」としては意味を持たない（未検証）。測れるのは仕組み（数・止まり方・取り消し）だけ。
- モデルの名前が設定と違えば 400 で断る（本物の検証の失敗と同じ形）。
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import struct
import sys
import time
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness_config import COMFY_IN, COMFY_OUT, COMFY_PORT, DIFFUSION  # noqa: E402

STEP_SEC = float(os.environ.get("P60_MOCK_STEP_SEC", "1.0"))
POOL_DIR = Path(os.environ.get("P60_MOCK_POOL", str(COMFY_OUT)))
MOCK_OUT = COMFY_OUT.parent / "mock_out"
POOL = sorted(p for p in POOL_DIR.glob("p60_a-*.png"))  # (a) の 320px の絵だけ
ALLOWED = {DIFFUSION["model"].get(k) for k in ("unet_name", "clip_name", "vae_name")} - {None}

app = FastAPI()
QUEUE: list[tuple[int, str, dict]] = []
RUNNING: dict | None = None
HISTORY: dict[str, dict] = {}
CLIENTS: set[WebSocket] = set()
_number = 0
_wake = asyncio.Event()


def _ms() -> int:
    return int(time.time() * 1000)


async def _send(msg: dict | bytes) -> None:
    for ws in list(CLIENTS):
        try:
            if isinstance(msg, bytes):
                await ws.send_bytes(msg)
            else:
                await ws.send_text(json.dumps(msg))
        except Exception:
            CLIENTS.discard(ws)


def _validate(prompt: dict) -> dict | None:
    for nid, node in prompt.items():
        for k, v in node.get("inputs", {}).items():
            if k in ("unet_name", "clip_name", "vae_name") and v not in ALLOWED:
                return {nid: {"errors": [{"type": "value_not_in_list", "message": f"{k}: {v}"}]}}
    return None


def _pick(prompt: dict) -> tuple[Image.Image, tuple[int, int]]:
    texts, seed, size = [], 0, (320, 320)
    for node in prompt.values():
        inp = node.get("inputs", {})
        if isinstance(inp.get("text"), str):
            texts.append(inp["text"])
        if "seed" in inp:
            seed = inp["seed"]
        elif "noise_seed" in inp:
            seed = inp["noise_seed"]
        if "width" in inp and "height" in inp and isinstance(inp["width"], int):
            size = (inp["width"], inp["height"])
    h = int(hashlib.sha256(json.dumps([seed, sorted(texts)]).encode()).hexdigest(), 16)
    return Image.open(POOL[h % len(POOL)]).convert("RGB"), size


def _make_image(prompt: dict) -> Image.Image:
    img, size = _pick(prompt)
    src = mask = None
    for nid, node in prompt.items():
        if nid == "source":
            src = Image.open(COMFY_IN / node["inputs"]["image"]).convert("RGB")
        if nid == "protected_mask":
            mask = Image.open(COMFY_IN / node["inputs"]["image"]).convert("L")
    if src is not None:
        size = src.size
    img = img.resize(size)
    if src is not None and mask is not None:
        img.paste(src, (0, 0), mask.resize(size).point(lambda v: 255 if v > 127 else 0))
    return img


async def _execute(pid: str, prompt: dict) -> None:
    global RUNNING
    start = _ms()
    msgs = [["execution_start", {"prompt_id": pid, "timestamp": start}]]
    await _send({"type": "execution_start", "data": {"prompt_id": pid, "timestamp": start}})
    steps = next((n["inputs"]["steps"] for n in prompt.values() if "steps" in n.get("inputs", {})), 8)
    final = _make_image(prompt)
    await _send({"type": "executing", "data": {"node": "sampler", "prompt_id": pid}})
    for i in range(steps):
        await asyncio.sleep(STEP_SEC)
        if RUNNING and RUNNING.get("interrupt"):
            msgs.append(["execution_interrupted", {"prompt_id": pid, "timestamp": _ms()}])
            HISTORY[pid] = {"prompt": [0, pid, prompt, {}, []], "outputs": {},
                            "status": {"status_str": "error", "completed": False, "messages": msgs}}
            await _send({"type": "execution_interrupted", "data": {"prompt_id": pid}})
            await _send({"type": "executing", "data": {"node": None, "prompt_id": pid}})
            return
        await _send({"type": "progress", "data": {"value": i + 1, "max": steps, "prompt_id": pid, "node": "sampler"}})
        prev = final.resize((64, 64)).filter(ImageFilter.GaussianBlur(max(0.1, 6 * (1 - (i + 1) / steps))))
        buf = io.BytesIO()
        prev.save(buf, "JPEG")
        await _send(struct.pack(">II", 1, 1) + buf.getvalue())
    MOCK_OUT.mkdir(parents=True, exist_ok=True)
    name = f"mock_{pid}.png"
    final.save(MOCK_OUT / name)
    msgs.append(["execution_success", {"prompt_id": pid, "timestamp": _ms()}])
    HISTORY[pid] = {"prompt": [0, pid, prompt, {}, []],
                    "outputs": {"save": {"images": [{"filename": name, "subfolder": "", "type": "output"}]}},
                    "status": {"status_str": "success", "completed": True, "messages": msgs}}
    await _send({"type": "executing", "data": {"node": None, "prompt_id": pid}})


async def _runner() -> None:
    global RUNNING
    while True:
        while not QUEUE:
            _wake.clear()
            await _wake.wait()
        _, pid, prompt = QUEUE.pop(0)
        RUNNING = {"pid": pid, "prompt": prompt, "interrupt": False}
        try:
            await _execute(pid, prompt)
        finally:
            RUNNING = None


@app.on_event("startup")
async def _start() -> None:
    asyncio.create_task(_runner())


@app.get("/system_stats")
async def system_stats():
    return {"system": {"comfyui_version": "mock-of-0.39.2"}, "devices": []}


@app.post("/prompt")
async def post_prompt(req: Request):
    global _number
    body = await req.json()
    prompt = body["prompt"]
    err = _validate(prompt)
    if err:
        return JSONResponse({"error": {"type": "prompt_outputs_failed_validation"}, "node_errors": err}, 400)
    pid = body.get("prompt_id") or str(uuid.uuid4())
    _number += 1
    QUEUE.append((_number, pid, prompt))
    _wake.set()
    return {"prompt_id": pid, "number": _number, "node_errors": {}}


@app.get("/queue")
async def get_queue():
    run = [[0, RUNNING["pid"], {}, {}, []]] if RUNNING else []
    return {"queue_running": run, "queue_pending": [[n, p, {}, {}, []] for n, p, _ in QUEUE]}


@app.post("/queue")
async def post_queue(req: Request):
    body = await req.json()
    dels = set(body.get("delete", []))
    QUEUE[:] = [x for x in QUEUE if x[1] not in dels]
    if body.get("clear"):
        QUEUE.clear()
    return {}


@app.post("/interrupt")
async def interrupt(req: Request):
    try:
        body = await req.json()
    except Exception:
        body = {}
    pid = body.get("prompt_id")
    if RUNNING and (pid is None or pid == RUNNING["pid"]):
        RUNNING["interrupt"] = True
    return {}


@app.get("/history")
async def history_all(max_items: int | None = None):
    return HISTORY


@app.get("/history/{pid}")
async def history_one(pid: str):
    return {pid: HISTORY[pid]} if pid in HISTORY else {}


@app.post("/upload/image")
async def upload(image: UploadFile, request: Request):
    COMFY_IN.mkdir(parents=True, exist_ok=True)
    (COMFY_IN / image.filename).write_bytes(await image.read())
    return {"name": image.filename, "subfolder": "", "type": "input"}


@app.get("/view")
async def view(filename: str, subfolder: str = "", type: str = "output"):
    return Response((MOCK_OUT / filename).read_bytes(), media_type="image/png")


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    CLIENTS.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        CLIENTS.discard(websocket)


if __name__ == "__main__":
    if not POOL:
        raise SystemExit(f"選ぶ元の絵が無い：{POOL_DIR}")
    uvicorn.run(app, host="127.0.0.1", port=COMFY_PORT, log_level="warning")
