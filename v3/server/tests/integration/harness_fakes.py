"""ハーネスの試験と画面の確認に使う偽物（どれも偽物。本物の ComfyUI・LLM・検出器の振る舞いを確かめる物ではない）。

- FakeComfyServer：偽の ComfyUI。本当に口を開ける（uvicorn）。/prompt・/history・/view・/upload/image・/queue・
  /interrupt と、/ws の進み具合（progress の文字の知らせと、途中の絵の2進の枠）を返す。1件ずつ順に「実行」する
- fake_llm：LiteLLM の送り手の差し替え。問いの出力の形の行を見て、形の合う答えを返す（中身は台本 script で変える）
- fake_detector：検出器の送り手の差し替え。人物と文字の範囲を返す（台本で変える）
"""

import asyncio
import hashlib
import io
import json
import re
import socket
import struct
from typing import Any

import uvicorn
from fastapi import FastAPI, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from PIL import Image, ImageDraw

from v3server.service_senders.sender_result_types import AdapterResult


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _png(w: int, h: int, seed: int, step: int | None = None, total: int | None = None) -> bytes:
    hue = seed % 360
    im = Image.new("RGB", (w, h), (235, 225, 200))
    d = ImageDraw.Draw(im)
    r = (hue * 7) % 120 + 80
    upto = w if step is None else max(1, int(w * step / max(total or 1, 1)))
    for x in range(0, upto, 4):
        d.line([(x, 0), (x, h)], fill=(r, 150 - (x * 60 // max(w, 1)), 110))
    d.ellipse([w * 0.3, h * 0.2, w * 0.7, h * 0.8], outline=(60, 50, 40), width=3)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


class FakeComfyServer:
    """偽の ComfyUI。step_seconds × steps で1件を「実行」する。"""

    def __init__(self, steps: int = 6, step_seconds: float = 0.15):
        self.steps, self.step_seconds = steps, step_seconds
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.prompts: dict[str, dict[str, Any]] = {}
        self.order: list[str] = []
        self.pending: list[str] = []
        self.running: str | None = None
        self.history: dict[str, dict[str, Any]] = {}
        self.interrupted: set[str] = set()
        self.interrupt_calls: list[Any] = []
        self.sockets: dict[str, WebSocket] = {}
        self.uploads: dict[str, bytes] = {}
        self._wake = asyncio.Event()
        self.app = self._build()

    def _build(self) -> FastAPI:
        app = FastAPI()

        @app.post("/prompt")
        async def prompt(req: Request):
            body = await req.json()
            pid = f"fake-{len(self.order) + 1}"
            self.prompts[pid] = {"prompt": body["prompt"], "client_id": body.get("client_id")}
            self.order.append(pid)
            self.pending.append(pid)
            self._wake.set()
            return {"prompt_id": pid, "number": len(self.order)}

        @app.get("/history/{pid}")
        async def history(pid: str):
            return {pid: self.history[pid]} if pid in self.history else {}

        @app.get("/queue")
        async def queue():
            return {"queue_running": [[0, self.running, {}, {}, []]] if self.running else [],
                    "queue_pending": [[i + 1, p, {}, {}, []] for i, p in enumerate(self.pending)]}

        @app.post("/queue")
        async def queue_delete(req: Request):
            body = await req.json()
            for p in body.get("delete", []):
                if p in self.pending:
                    self.pending.remove(p)
            return {}

        @app.post("/interrupt")
        async def interrupt(req: Request):
            body = await req.json() if await req.body() else {}
            self.interrupt_calls.append(body)
            pid = body.get("prompt_id")
            if pid is None or pid == self.running:
                self.interrupted.add(self.running)
            return {}

        @app.post("/upload/image")
        async def upload(image: UploadFile):
            self.uploads[image.filename] = await image.read()
            return {"name": image.filename, "subfolder": "", "type": "input"}

        @app.get("/view")
        async def view(filename: str, subfolder: str = "", type: str = "output"):
            pid = filename.split(".")[0]
            w, h, seed = self._size(self.prompts[pid]["prompt"])
            return Response(_png(w, h, seed), media_type="image/png")

        @app.websocket("/ws")
        async def ws(websocket: WebSocket, clientId: str):
            await websocket.accept()
            self.sockets[clientId] = websocket
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                self.sockets.pop(clientId, None)

        return app

    def _size(self, prompt: dict[str, Any]) -> tuple[int, int, int]:
        seed = 0
        for n in prompt.values():
            if "seed" in n.get("inputs", {}) and isinstance(n["inputs"]["seed"], int):
                seed = n["inputs"]["seed"]
        lat = next((n for n in prompt.values() if n["class_type"] == "EmptyLatentImage"), None)
        if lat is not None:
            return lat["inputs"]["width"], lat["inputs"]["height"], seed
        src = next((n for n in prompt.values() if n["class_type"] == "LoadImage"), None)
        if src is not None and src["inputs"].get("image") in self.uploads:
            im = Image.open(io.BytesIO(self.uploads[src["inputs"]["image"]]))
            return im.width, im.height, seed
        return 512, 512, seed

    async def _send(self, client_id: str | None, data: Any) -> None:
        ws = self.sockets.get(client_id or "")
        if ws is None:
            return
        try:
            if isinstance(data, bytes):
                await ws.send_bytes(data)
            else:
                await ws.send_text(json.dumps(data))
        except Exception:  # 偽物：受け手が切れたら送らない
            self.sockets.pop(client_id or "", None)

    async def _executor(self) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            while self.pending:
                pid = self.pending.pop(0)
                self.running = pid
                cid = self.prompts[pid]["client_id"]
                w, h, seed = self._size(self.prompts[pid]["prompt"])
                await self._send(cid, {"type": "execution_start", "data": {"prompt_id": pid}})
                stopped = False
                for i in range(1, self.steps + 1):
                    await asyncio.sleep(self.step_seconds)
                    if pid in self.interrupted:
                        stopped = True
                        break
                    await self._send(cid, {"type": "progress", "data": {"value": i, "max": self.steps,
                                                                        "prompt_id": pid, "node": "3"}})
                    small = _png(max(8, w // 4), max(8, h // 4), seed, i, self.steps)
                    await self._send(cid, struct.pack(">II", 1, 2) + small)
                if stopped:
                    self.history[pid] = {"status": {"status_str": "error", "messages": [
                        ["execution_interrupted", {"node_type": "KSampler", "prompt_id": pid}]]}, "outputs": {}}
                    await self._send(cid, {"type": "execution_interrupted", "data": {"prompt_id": pid}})
                else:
                    self.history[pid] = {"status": {"status_str": "success", "messages": []}, "outputs": {
                        "9": {"images": [{"filename": f"{pid}.png", "subfolder": "", "type": "output"}]}}}
                    await self._send(cid, {"type": "execution_success", "data": {"prompt_id": pid}})
                self.running = None

    async def start(self) -> None:
        cfg = uvicorn.Config(self.app, host="127.0.0.1", port=self.port, log_level="warning", lifespan="off")
        self.server = uvicorn.Server(cfg)
        self._tasks = [asyncio.create_task(self.server.serve()), asyncio.create_task(self._executor())]
        while not self.server.started:
            await asyncio.sleep(0.05)

    async def stop(self) -> None:
        self.server.should_exit = True
        self._tasks[1].cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)


# ---------------------------------------------------------------- LLM・検出器


class Script:
    """偽の LLM・検出器の答えを、試験ごとに変える台本。"""

    def __init__(self):
        self.persons = 1            # 検出する人数
        self.touch = ""             # 見切れ（T/B/L/R）
        self.texts = 0              # 絵の中の文字の範囲の数
        self.texts_calls = None     # 文字を返す /text_regions の回数（None なら毎回。直した後は消えた、を作る）
        self.person_box = (10, 10, 100, 200)
        self.hands = 1
        self.same = True            # /identity_ccip の答え（同じ人物か）
        self.same_calls = None      # 「違う」を返す回数（None なら same のまま。直した後は同じ、を作る）
        self.shot = "胸から上"
        self.angle = "目の高さ"
        self.pair = "content"       # content（絵の中身で決まる。入れ替えても同じ答え）/ tie / a（いつも A。入れ替えると食い違う）/ flip（くり返すたびに好みが逆）
        self.tags_broken = False
        self.llm_sleep = 0.0
        self.detector_sleep = 0.0
        self.calls: list[tuple[str, str]] = []
        self._pair_calls = 0
        self.name_pages: list[dict[str, Any]] | None = None
        self.answers: dict[str, Any] = {}   # 工程の問いの答え（kind → JSON にする値）

    def kind_of(self, text: str) -> str:
        if '{"tags"' in text:
            return "tags"
        if '"items":[{"image"' in text:
            return "shot_angle"
        if '{"pairs":[{"id"' in text:
            return "pair"
        if '"issues":[{"line":"行の番号","why"' in text:
            return "contradiction"
        if '"kind":"未回収' in text:
            return "foreshadow"
        for kind, mark in STAGE_QUESTION_MARKS:
            if mark in text:
                return kind
        if '"pages"' in text:
            return "name_draft"
        return "other"


# 工程の問い（S0〜S2・S6）の出力の形の行に入る印。llm_questions の各問いの _FORMAT と合わせる
STAGE_QUESTION_MARKS = (
    ("plan_interview", '"questions":[{"ask"'),
    ("structure_views", '"views":[{"view"'),
    ("structure", '"pages":[{"page":ページの番号,"summary"'),
    ("settings_sheet", '"characters":[{"name"'),
    ("distinguish", '"confusable":[{"a"'),
    ("page_summary", '"pages":[{"image"'),
    ("outline_compare", '"gaps":[{"page"'),
    ("layout_tiers", '"tiers"'),
    ("reading_order", '"order"'),
    ("imported_text", '"suspicious"'),
)


def _text_of(messages: list[dict[str, Any]]) -> tuple[str, int]:
    parts = messages[-1]["content"]
    if isinstance(parts, str):
        return parts, 0
    text = "".join(p.get("text", "") for p in parts if p["type"] == "text")
    return text, sum(1 for p in parts if p["type"] == "image_url")


def _images_of(messages: list[dict[str, Any]]) -> list[str]:
    parts = messages[-1]["content"]
    return [] if isinstance(parts, str) else [p["image_url"]["url"] for p in parts if p["type"] == "image_url"]


def _pair_answer(script: Script, text: str, images: list[str]) -> str:
    """組ごとに A・B・同じ。content は絵の中身の指紋の小さい方を選ぶ（左右を入れ替えても、くり返しても同じ答え）。"""
    names = text.split("次の名前で呼びます。\n")[1].split("\n\n")[0].splitlines()
    finger = {n: hashlib.sha256(u.encode()).hexdigest() for n, u in zip(names, images, strict=True)}
    script._pair_calls += 1
    flip = script.pair == "flip" and ((script._pair_calls - 1) // 2) % 2 == 1
    out = []
    for m in re.finditer(r"組(\d+)：A＝(\S+)　B＝(\S+)", text):
        i, a, b = int(m.group(1)), m.group(2), m.group(3)
        if script.pair == "tie":
            choice = "同じ"
        elif script.pair == "a":
            choice = "A"
        else:
            a_wins = finger[a] < finger[b]
            choice = "A" if a_wins != flip else "B"
        out.append({"id": i, "choice": choice})
    return json.dumps({"pairs": out}, ensure_ascii=False)


def fake_llm(script: Script):
    async def call(service, sp, request) -> AdapterResult:
        text, n_images = _text_of(request["messages"])
        kind = script.kind_of(text)
        script.calls.append(("llm", kind))
        if script.llm_sleep:
            await asyncio.sleep(script.llm_sleep)
        if kind == "tags":
            answer = "形が崩れた答え" if script.tags_broken else json.dumps({"tags": "1girl, standing, smile"})
        elif kind == "shot_angle":
            answer = json.dumps({"items": [{"image": i + 1, "shot": script.shot, "angle": script.angle,
                                            "facing": None} for i in range(n_images)]}, ensure_ascii=False)
        elif kind == "pair":
            answer = _pair_answer(script, text, _images_of(request["messages"]))
        elif kind == "contradiction":
            answer = json.dumps({"issues": []})
        elif kind == "foreshadow":
            answer = json.dumps({"issues": []})
        elif kind == "name_draft":
            answer = json.dumps({"pages": script.name_pages}, ensure_ascii=False)
        elif kind in script.answers:
            value = script.answers[kind]
            answer = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        else:
            answer = "{}"
        return AdapterResult(output={"text": answer}, model="fake")
    return call


def fake_detector(script: Script):
    async def call(service, sp, request) -> AdapterResult:
        ep = request["endpoint"]
        script.calls.append(("detector", ep))
        if script.detector_sleep:
            await asyncio.sleep(script.detector_sleep)
        if ep == "/person_face_head":
            x0, y0, x1, y1 = script.person_box
            persons = [{"x0": x0, "y0": y0, "x1": x1, "y1": y1, "score": 0.9, "h_ratio": 0.5, "area_ratio": 0.2,
                        "touch": script.touch if i == 0 else ""} for i in range(script.persons)]
            faces = [{"x0": x0 + 10, "y0": y0, "x1": x0 + 50, "y1": y0 + 40, "score": 0.9, "h_ratio": 0.2,
                      "area_ratio": 0.05, "touch": ""} for _ in range(script.persons)]
            return AdapterResult(output={"persons": persons, "faces": faces, "heads": []}, model="fake-detector")
        if ep == "/text_regions":
            n = script.texts
            if script.texts_calls is not None:
                n = n if script.texts_calls > 0 else 0
                script.texts_calls -= 1
            return AdapterResult(output={"texts": [{"x0": 0, "y0": 0, "x1": 16, "y1": 16, "score": 0.8}
                                                   for _ in range(n)]}, model="fake-detector")
        if ep == "/hands":
            return AdapterResult(output={"width": 0, "height": 0, "hands": [
                {"x0": 20, "y0": 60, "x1": 40, "y1": 80, "score": 0.7} for _ in range(script.hands)]},
                model="fake-detector")
        if ep == "/identity_ccip":
            same = script.same
            if script.same_calls is not None:
                same = script.same if script.same_calls <= 0 else not script.same
                script.same_calls -= 1
            t = float(request.get("form", {}).get("threshold", 0.178))
            return AdapterResult(output={"difference": t / 2 if same else t * 2, "threshold": t, "same": same},
                                 model="fake-detector")
        if ep == "/age_rating":
            return AdapterResult(output={"rating": {"general": 0.9, "sensitive": 0.08, "questionable": 0.02}},
                                 model="fake-detector")
        return AdapterResult(output={}, model="fake-detector")
    return call
