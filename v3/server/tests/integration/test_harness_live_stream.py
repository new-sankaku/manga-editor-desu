"""画面への出来事の流れ（live_stream.stream）。Temporal は使わない（速い組で流す）。"""

import asyncio
import json

from conftest import new_work, user

from v3server.database_engine import get_sessionmaker
from v3server.harness import live_stream
from v3server.harness.harness_record import add_event


async def _next_event(it) -> dict:
    while True:
        chunk = await asyncio.wait_for(anext(it), 5)
        if chunk.startswith("id: "):
            return json.loads(chunk.split("data: ", 1)[1])


async def test_確定の遅れた出来事も_大きいidを流した後で流す(api, monkeypatch):
    """上流を見る所は、古い印の出来事を書いて（id が決まる）から残りの作業を見て、最後に確定する。その間に別の所が
    書いて確定した出来事を先に流すと、id の境だけで読む流れは遅れた出来事を二度と流さなかった（画面の試験で、古い印が
    画面に出なかった）。"""
    monkeypatch.setattr(live_stream, "POLL_SECONDS", 0.01)
    wid = (await new_work(api, user()))["work"]
    closed = False

    async def disconnected() -> bool:
        return closed

    it = live_stream.stream(wid, 0, disconnected)
    late = get_sessionmaker()()
    try:
        await add_event(late, wid, "stale", {"n": "late"})  # id は決まったが、まだ確定しない
        async with get_sessionmaker()() as s:
            await add_event(s, wid, "unit", {"n": "early"})
            await s.commit()
        assert (await _next_event(it))["n"] == "early"
        await late.commit()
        assert (await _next_event(it))["n"] == "late"
        # 同じ出来事は2回流さない
        async with get_sessionmaker()() as s:
            await add_event(s, wid, "unit", {"n": "next"})
            await s.commit()
        assert (await _next_event(it))["n"] == "next"
    finally:
        closed = True
        await late.close()
        await it.aclose()
