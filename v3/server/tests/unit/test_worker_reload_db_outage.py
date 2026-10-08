"""作業者の読み直しが PostgreSQL に届かなくても、プロセスが終わらないことの試験（既製品は使わない）。

前は WorkerSet の読み直し（つなぎ先の一覧を読む）が OperationalError で落ちると、作業者のプロセスごと終わり、
PostgreSQL が戻っても生成・書き出し・ハーネスが進まなかった（2026-10-08 保存と再起動の確かめの場面 e で見つけた。
V3サーバーの土台「保存と再起動の確かめ」）。
"""

import asyncio

import pytest
from sqlalchemy.exc import OperationalError

from v3server.generation_queue import queue_worker_main
from v3server.generation_queue.queue_worker_main import WorkerSet


async def test_読み直しがDBに届かなくても続け_戻ったら読み直す(monkeypatch):
    monkeypatch.setattr(queue_worker_main, "RELOAD_SECONDS", 0.01)
    calls: list[str] = []
    back = asyncio.Event()

    async def reload(self):
        calls.append("try")
        if len(calls) <= 3:
            raise OperationalError("select", {}, ConnectionRefusedError("connection refused"))
        back.set()

    monkeypatch.setattr(WorkerSet, "reload", reload)
    task = asyncio.create_task(WorkerSet(client=None).keep_reloading())
    await asyncio.wait_for(back.wait(), 5)
    assert not task.done(), "DB に届かない間も読み直しを続ける"
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(calls) >= 4


async def test_DB以外の失敗は隠さない(monkeypatch):
    monkeypatch.setattr(queue_worker_main, "RELOAD_SECONDS", 0.01)

    async def reload(self):
        raise ValueError("つなぎ先の設定がおかしい")

    monkeypatch.setattr(WorkerSet, "reload", reload)
    with pytest.raises(ValueError):
        await asyncio.wait_for(WorkerSet(client=None).keep_reloading(), 5)
