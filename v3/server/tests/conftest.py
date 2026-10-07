"""試験は compose の PostgreSQL（v3_test）・OpenFGA・Temporal を実際に使う。先に `docker compose up -d` しておく。"""

import asyncio
import os
import subprocess
import time
import uuid

TEST_DB = "postgresql+psycopg://v3:v3@localhost:55432/v3_test"
os.environ["V3_DATABASE_URL"] = TEST_DB
os.environ["V3_DEV_AUTH"] = "1"

import httpx  # noqa: E402
import pytest  # noqa: E402
from temporalio.client import Client  # noqa: E402

from v3server.api.app import app  # noqa: E402
from v3server.authz import open_authz  # noqa: E402
from v3server.config import get_settings  # noqa: E402
from v3server.db import get_sessionmaker  # noqa: E402
from v3server.queue import adapters  # noqa: E402
from v3server.queue.worker import WorkerSet  # noqa: E402


def _alembic(*args: str) -> None:
    subprocess.run(["alembic", *args], check=True, env={**os.environ, "V3_DATABASE_URL": TEST_DB},
                   capture_output=True)


@pytest.fixture(scope="session", autouse=True)
def schema():
    _alembic("downgrade", "base")
    _alembic("upgrade", "head")


@pytest.fixture(scope="session")
async def authz(schema):
    async with get_sessionmaker()() as session:
        return await open_authz(session)


@pytest.fixture(scope="session")
async def temporal():
    return await Client.connect(get_settings().temporal_address)


@pytest.fixture(scope="session")
async def api(authz, temporal):
    app.state.authz = authz
    app.state.temporal = temporal
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture(scope="session")
async def workers(temporal):
    ws = WorkerSet(temporal)
    await ws.start()
    yield ws
    await ws.shutdown()


@pytest.fixture
def fake_adapter(monkeypatch):
    """つなぎ先への送信を差し替える。request["script"] の順に振る舞う（呼ばれた回数で進む）。"""
    state = {"calls": [], "running": 0, "max_running": 0}

    async def fake(service, sp, request):
        state["calls"].append((service.name, request.get("tag")))
        state["running"] += 1
        state["max_running"] = max(state["max_running"], state["running"])
        try:
            await asyncio.sleep(request.get("sleep", 0))
            n = sum(1 for _, tag in state["calls"] if tag == request.get("tag"))
            script = request.get("script", [])
            step = script[n - 1] if n - 1 < len(script) else "ok"
            if step != "ok":
                raise adapters.AdapterError(step, f"試験: {step}", retry_after=1 if step == "rate_limited" else None)
            return adapters.AdapterResult(output={"text": f"ok:{request.get('tag')}"}, model="fake")
        finally:
            state["running"] -= 1

    monkeypatch.setitem(adapters.ADAPTERS, "litellm", fake)
    return state


def user() -> str:
    return f"u-{uuid.uuid4().hex[:8]}"


def h(u: str) -> dict[str, str]:
    return {"X-V3-User": u}


async def wait_for(fn, timeout: float = 30, interval: float = 0.2):
    deadline = time.monotonic() + timeout
    while True:
        value = await fn()
        if value:
            return value
        if time.monotonic() > deadline:
            raise AssertionError("時間内に条件を満たさなかった")
        await asyncio.sleep(interval)


async def new_work(api: httpx.AsyncClient, author: str) -> dict[str, str]:
    """作品・巻・話・ページ2枚を作る。"""
    r = await api.post("/works", headers=h(author), json={
        "title": "試験", "reading_direction": "rtl", "text_direction": "vertical", "medium": "paper"})
    assert r.status_code == 201, r.text
    wid = r.json()["id"]
    ids = {"work": wid, "volume": uuid.uuid4().hex, "episode": uuid.uuid4().hex,
           "page1": uuid.uuid4().hex, "page2": uuid.uuid4().hex}
    for op in [
        {"type": "add_volume", "id": ids["volume"], "number": 1},
        {"type": "add_episode", "id": ids["episode"], "volume_id": ids["volume"], "number": 1},
        {"type": "add_page", "id": ids["page1"], "episode_id": ids["episode"], "number": 1},
        {"type": "add_page", "id": ids["page2"], "episode_id": ids["episode"], "number": 2},
    ]:
        r = await api.post(f"/works/{wid}/ops", headers=h(author), json=op)
        assert r.status_code == 200, r.text
    return ids
