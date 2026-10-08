"""ComfyUI への送信（P60 用の小さい作り）。
- 依頼の番号（prompt_id）は呼ぶ側が決める。同じ番号の依頼が待ち・実行中・履歴にあれば送らずにそれを待つ
  （作業者が落ちて活動がやり直されても、同じ絵を2回作らないため。ComfyUI は同じ番号を2回受け付けてしまう）。
- 取り消し：待ちの物は /queue の削除、実行中の物は /interrupt（p56 の結果）。
"""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any, Callable

import httpx

from harness_config import COMFY_URL

NS = uuid.UUID("6f6b2c4e-6060-4d0a-9c60-600000000060")


def prompt_id_for(key: str) -> str:
    return str(uuid.uuid5(NS, key))


class ComfyError(Exception):
    def __init__(self, kind: str, msg: str):
        super().__init__(msg)
        self.kind = kind  # transport・refused・failed・interrupted


async def _get(c: httpx.AsyncClient, path: str) -> Any:
    try:
        r = await c.get(path)
    except httpx.HTTPError as e:
        raise ComfyError("transport", f"{path}: {e}") from e
    if r.status_code >= 500:
        raise ComfyError("transport", f"{path} が {r.status_code}")
    r.raise_for_status()
    return r.json()


async def queue_state(c: httpx.AsyncClient) -> tuple[list[str], list[str]]:
    q = await _get(c, "/queue")
    return [x[1] for x in q.get("queue_running", [])], [x[1] for x in q.get("queue_pending", [])]


async def history_entry(c: httpx.AsyncClient, pid: str) -> dict | None:
    h = await _get(c, f"/history/{pid}")
    return h.get(pid)


async def history_count() -> int:
    async with httpx.AsyncClient(base_url=COMFY_URL, timeout=30) as c:
        return len(await _get(c, "/history?max_items=100000"))


async def upload_image(path: Path, name: str) -> str:
    async with httpx.AsyncClient(base_url=COMFY_URL, timeout=60) as c:
        r = await c.post("/upload/image", files={"image": (name, path.read_bytes(), "image/png")},
                         data={"type": "input", "overwrite": "true"})
        if r.status_code >= 400:
            raise ComfyError("refused" if r.status_code < 500 else "transport", f"/upload/image {r.status_code}")
        return r.json()["name"]


async def run_prompt(prompt: dict, pid: str, on_wait: Callable[[str], Any], base_url: str = COMFY_URL,
                     on_sent: Callable[[], Any] | None = None) -> tuple[bytes, dict]:
    """番号 pid で送って終わりを待ち、出来た絵1枚の中身と記録を返す。
    on_wait(状態) を約1秒ごとに呼ぶ（状態：pending・running）。活動の生存の知らせに使う。
    取り消されたら（CancelledError）その番号の依頼を消すか止めてから上げ直す。
    同じ番号の履歴が失敗・中断で終わっていたら（一時停止で止めた後の再開など）、同じ番号で送り直す。"""
    sent_now = False
    async with httpx.AsyncClient(base_url=base_url, timeout=30) as c:
        try:
            running, pending = await queue_state(c)
            existing = await history_entry(c, pid)
            finished_ok = existing is not None and existing.get("status", {}).get("status_str") == "success"
            if not finished_ok and pid not in running and pid not in pending:
                try:
                    r = await c.post("/prompt", json={"prompt": prompt, "prompt_id": pid})
                except httpx.HTTPError as e:
                    raise ComfyError("transport", f"/prompt: {e}") from e
                if r.status_code >= 500:
                    raise ComfyError("transport", f"/prompt {r.status_code}")
                if r.status_code >= 400:
                    raise ComfyError("refused", f"/prompt {r.status_code}: {r.text[:300]}")
                sent_now = True
                if on_sent:
                    on_sent()  # 送った直後に記録する（作業者が実行中に落ちても送った回が数えられる）
            while True:
                entry = await history_entry(c, pid)
                if entry is not None and (finished_ok or entry is not existing and entry != existing):
                    break
                running, pending = await queue_state(c)
                if pid not in running and pid not in pending:
                    # 履歴に無く待ちにも無い：消された
                    raise ComfyError("interrupted", "待ちから消された")
                on_wait("running" if pid in running else "pending")
                await asyncio.sleep(1.0)
            status = entry.get("status", {})
            if status.get("status_str") != "success":
                msgs = [m[0] for m in status.get("messages", [])]
                kind = "interrupted" if "execution_interrupted" in msgs else "failed"
                raise ComfyError(kind, f"実行の結果 {status.get('status_str')} {msgs}")
            imgs = [im for out in entry["outputs"].values() for im in out.get("images", [])]
            if not imgs:
                raise ComfyError("failed", "出力に絵が無い")
            im = imgs[0]
            r = await c.get("/view", params={"filename": im["filename"], "subfolder": im["subfolder"], "type": im["type"]})
            r.raise_for_status()
            return r.content, {"sent_now": sent_now, "image": im}
        except asyncio.CancelledError:
            await cancel_prompts([pid], base_url)
            raise


async def cancel_prompts(pids: list[str], base_url: str = COMFY_URL) -> dict:
    """待ちの物は消し、実行中の物は止める。消した数と止めた数を返す。"""
    removed, interrupted = 0, 0
    async with httpx.AsyncClient(base_url=base_url, timeout=30) as c:
        running, pending = await queue_state(c)
        dels = [p for p in pids if p in pending]
        if dels:
            await c.post("/queue", json={"delete": dels})
            removed = len(dels)
        for p in pids:
            if p in running:
                await c.post("/interrupt", json={"prompt_id": p})
                interrupted += 1
    return {"removed": removed, "interrupted": interrupted}


async def orphan_prompts(known_active: set[str]) -> list[str]:
    """待ち・実行中に残っている依頼のうち、どの作業も待っていない物。"""
    async with httpx.AsyncClient(base_url=COMFY_URL, timeout=30) as c:
        running, pending = await queue_state(c)
    return [p for p in running + pending if p not in known_active]
