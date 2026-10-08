"""試験は compose の PostgreSQL・OpenFGA・Temporal を実際に使う。先に `docker compose up -d` しておく。

データベースは、流すたびに新しく作る（v3_test_<ランダム>）。終わったら消す。前は v3_test を全員で使い、別の作業の試験が
始めに表を全部消して作り直す（downgrade base）ので、流している途中の試験が落ちることがあった（2026-10-08）。
OpenFGA のストアはデータベースに id を持つので、データベースを分けるとストアも分かれる。"""

import asyncio
import os
import subprocess
import time
import uuid

from sqlalchemy.engine import make_url

from v3server.server_settings import Settings, get_settings

# 試験の DB のサーバーは、.env の V3_DATABASE_URL と同じ。V3_TEST_DATABASE_URL で替えられる（名前は v3_test の代わりの頭に使う）。
# 利用者は開発用の見出し（X-V3-User）で名乗り、絵は手元のフォルダに置く
_BASE_URL = make_url(os.environ.get("V3_TEST_DATABASE_URL") or make_url(Settings().database_url).set(database="v3_test"))
TEST_DB_NAME = f"{_BASE_URL.database}_{uuid.uuid4().hex[:10]}"
TEST_DB = _BASE_URL.set(database=TEST_DB_NAME).render_as_string(hide_password=False)
os.environ["V3_DATABASE_URL"] = TEST_DB
os.environ["V3_AUTH_MODE"] = "dev_header"
os.environ["V3_IMAGE_STORE"] = "local"
get_settings.cache_clear()

import httpx  # noqa: E402
import psycopg  # noqa: E402
import pytest  # noqa: E402
from temporalio.client import Client  # noqa: E402

from v3server.database_engine import get_sessionmaker  # noqa: E402
from v3server.generation_queue.queue_worker_main import WorkerSet  # noqa: E402
from v3server.http_routes.http_app_factory import app  # noqa: E402
from v3server.openfga_permissions import open_authz  # noqa: E402
from v3server.service_senders.sender_by_adapter_name import ADAPTERS  # noqa: E402
from v3server.service_senders.sender_result_types import AdapterError, AdapterResult  # noqa: E402


def _alembic(*args: str) -> None:
    subprocess.run(["alembic", *args], check=True, env={**os.environ, "V3_DATABASE_URL": TEST_DB},
                   capture_output=True)


def _maintenance(sql: str) -> None:
    """データベースを作る・消す（サーバーの postgres データベースにつないで流す）。"""
    url = _BASE_URL.set(database="postgres", drivername="postgresql")
    with psycopg.connect(url.render_as_string(hide_password=False), autocommit=True) as conn:
        conn.execute(sql)


@pytest.fixture(scope="session", autouse=True)
def schema():
    _maintenance(f'CREATE DATABASE "{TEST_DB_NAME}"')
    try:
        # 戻す移行も通ることを確かめてから作り直す
        _alembic("upgrade", "head")
        _alembic("downgrade", "base")
        _alembic("upgrade", "head")
        yield
    finally:
        _maintenance(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)')


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
                raise AdapterError(step, f"試験: {step}", retry_after=1 if step == "rate_limited" else None)
            return AdapterResult(output={"text": f"ok:{request.get('tag')}"}, model="fake")
        finally:
            state["running"] -= 1

    # 手元の先（make_service の location="local"）は、手元と言える送り手（comfyui・127.0.0.1）で登録するので、同じ偽にする
    monkeypatch.setitem(ADAPTERS, "litellm", fake)
    monkeypatch.setitem(ADAPTERS, "comfyui", fake)
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
