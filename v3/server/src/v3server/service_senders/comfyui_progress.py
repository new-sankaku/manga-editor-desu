"""ComfyUI の進み具合（段数）と途中の絵を受け、service_call_progress の表に書く（llm_doc/V3ハーネスの実装.md 6章）。

- 依頼の request に progress_key があるときだけ使う（comfyui_sender.py）。/prompt に client_id として同じ鍵を渡すと、
  ComfyUI はその鍵の WebSocket にだけ途中の絵を送る
- 進み具合は Temporal の履歴に流さない（AIハーネスのオープンソース実装の調査 5.1 の8）。画面へは SSE で送る
- WebSocket につながらなければ、表の state を unavailable にして生成は続ける（画面に「進み具合を受け取れない」と出す）
- 書く回数は鍵ごとに WRITE_INTERVAL 秒に1回まで。終わり・止まった・失敗は必ず書く

WebSocket の中身（ComfyUI のソースで確かめた。llm_doc/V3調査/AIハーネスのオープンソース実装の調査.md 3.16）
- 文字：{"type": "progress", "data": {"value", "max", "prompt_id"}}・execution_start・execution_success・
  execution_interrupted・execution_error
- バイナリ：先頭4バイトが種類（1 = 途中の絵、4 = 付帯情報付きの途中の絵）。1 は続く4バイトが形式（1 = JPEG、2 = PNG）、
  4 は続く4バイトが付帯情報の長さで、その後に JSON と絵
"""

import asyncio
import base64
import json
import logging
import struct
import time
from typing import Any

import websockets
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from v3server.canonical_tables.harness_tables import ServiceCallProgress
from v3server.database_engine import get_sessionmaker

log = logging.getLogger(__name__)

WRITE_INTERVAL = 0.3
CONNECT_TIMEOUT = 5

_FORMATS = {1: "image/jpeg", 2: "image/png"}


def parse_binary_frame(frame: bytes) -> tuple[str, bytes] | None:
    """途中の絵の枠を（形式, 絵）に読む。途中の絵でなければ None。"""
    if len(frame) < 8:
        return None
    kind = struct.unpack(">I", frame[:4])[0]
    if kind == 1:
        fmt = struct.unpack(">I", frame[4:8])[0]
        return _FORMATS.get(fmt, "application/octet-stream"), frame[8:]
    if kind == 4:
        n = struct.unpack(">I", frame[4:8])[0]
        meta = json.loads(frame[8:8 + n])
        return meta.get("image_type", "image/png"), frame[8 + n:]
    return None


def state_of_message(msg: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    """文字の知らせを（状態, 値）に読む。関係の無い知らせは (None, {})。"""
    t, d = msg.get("type"), msg.get("data") or {}
    if t == "progress":
        return "running", {"value": d.get("value"), "max": d.get("max"), "prompt_id": d.get("prompt_id")}
    if t == "execution_start":
        return "running", {"prompt_id": d.get("prompt_id")}
    if t == "execution_success":
        return "finished", {"prompt_id": d.get("prompt_id")}
    if t == "execution_interrupted":
        return "interrupted", {"prompt_id": d.get("prompt_id")}
    if t == "execution_error":
        return "error", {"prompt_id": d.get("prompt_id")}
    return None, {}


async def write_progress(key: str, **values: Any) -> None:
    async with get_sessionmaker()() as session:
        stamped = {**values, "updated_at": func.clock_timestamp()}
        # NOT NULL は衝突の判定より前に、入れようとした行で調べられる。state の無い書き込み（prompt_id だけ等）でも
        # 落ちないよう、入れる行には始まりの state を置く（行があれば set_ の項目だけ変わる）
        stmt = insert(ServiceCallProgress).values(progress_key=key, **{"state": "pending", **stamped})
        stmt = stmt.on_conflict_do_update(index_elements=["progress_key"], set_=stamped)
        await session.execute(stmt)
        await session.commit()


class ProgressListener:
    def __init__(self, endpoint: str, key: str):
        self.url = endpoint.replace("http://", "ws://").replace("https://", "wss://").rstrip("/") + f"/ws?clientId={key}"
        self.key = key
        self.prompt_id: str | None = None
        self._task: asyncio.Task | None = None
        self._last_write = 0.0
        self._pending: dict[str, Any] = {}

    async def start(self) -> None:
        await write_progress(self.key, state="pending", value=None, max=None)
        try:
            ws = await asyncio.wait_for(websockets.connect(self.url, max_size=None), CONNECT_TIMEOUT)
        except (TimeoutError, OSError, websockets.WebSocketException) as e:
            log.warning("ComfyUI の進み具合につながらない（%s）: %r", self.url, e)
            await write_progress(self.key, state="unavailable")
            return
        self._task = asyncio.create_task(self._read(ws))

    async def _flush(self, force: bool = False) -> None:
        if self._pending and (force or time.monotonic() - self._last_write >= WRITE_INTERVAL):
            values, self._pending = self._pending, {}
            self._last_write = time.monotonic()
            await write_progress(self.key, **values)

    async def _read(self, ws) -> None:
        try:
            async for frame in ws:
                if isinstance(frame, bytes):
                    got = parse_binary_frame(frame)
                    if got is not None:
                        self._pending.update(preview_media_type=got[0], preview_b64=base64.b64encode(got[1]).decode())
                else:
                    state, values = state_of_message(json.loads(frame))
                    pid = values.pop("prompt_id", None)
                    if state is None or (self.prompt_id is not None and pid not in (None, self.prompt_id)):
                        continue
                    self._pending.update(state=state, **{k: v for k, v in values.items() if v is not None})
                    if state != "running":
                        await self._flush(force=True)
                        continue
                await self._flush()
        except websockets.WebSocketException as e:
            log.warning("ComfyUI の進み具合が切れた: %r", e)
        finally:
            await ws.close()

    async def stop(self, final_state: str | None) -> None:
        if self._task is None:
            # つながらなかった。unavailable のまま残す
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        if final_state is not None:
            self._pending["state"] = final_state
        await self._flush(force=True)
