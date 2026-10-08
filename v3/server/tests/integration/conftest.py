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
XDIST_WORKER = os.environ.get("PYTEST_XDIST_WORKER")  # pytest-xdist で同時に流すときの作業者の名前（gw0 …）
TEST_DB_NAME = f"{_BASE_URL.database}_{uuid.uuid4().hex[:10]}"
TEST_DB = _BASE_URL.set(database=TEST_DB_NAME).render_as_string(hide_password=False)
os.environ["V3_DATABASE_URL"] = TEST_DB
os.environ["V3_AUTH_MODE"] = "dev_header"
os.environ["V3_IMAGE_STORE"] = "local"
get_settings.cache_clear()

import httpx  # noqa: E402
import psycopg  # noqa: E402
import pytest  # noqa: E402
from google.protobuf.duration_pb2 import Duration  # noqa: E402
from temporalio.api.workflowservice.v1 import DescribeNamespaceRequest, RegisterNamespaceRequest  # noqa: E402
from temporalio.client import Client, WorkflowFailureError  # noqa: E402
from temporalio.service import RPCError, RPCStatusCode  # noqa: E402
from temporalio.testing import WorkflowEnvironment  # noqa: E402

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
        # 戻す移行も通ることを確かめてから作り直す。同時に流すときは、確かめるのは1つの作業者（gw0）だけ（中身は同じ）
        _alembic("upgrade", "head")
        if XDIST_WORKER in (None, "gw0"):
            _alembic("downgrade", "base")
            _alembic("upgrade", "head")
        yield
    finally:
        _maintenance(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)')


@pytest.fixture(scope="session")
async def authz(schema):
    async with get_sessionmaker()() as session:
        return await open_authz(session)


# いくつも同時に流す（pytest-xdist）ときは、作業者（gw0, gw1 …）ごとに Temporal の名前空間を分ける。同じ名前空間だと、
# ほかの作業者が同じ待ち行列（v3-control・v3-export など）の依頼を取り、自分のデータベースに無い行を探して失敗する
TEMPORAL_NAMESPACE = f"v3test-{XDIST_WORKER}" if XDIST_WORKER else "default"


async def _ensure_namespace(address: str, namespace: str) -> None:
    """名前空間が無ければ作り、使えるようになるまで待つ。開発用の Temporal の中に残るので、作るのは初めの1回だけ。"""
    client = await Client.connect(address)
    try:
        await client.workflow_service.register_namespace(RegisterNamespaceRequest(
            namespace=namespace, workflow_execution_retention_period=Duration(seconds=24 * 3600)))
    except RPCError as e:
        if e.status != RPCStatusCode.ALREADY_EXISTS:
            raise
    deadline = time.monotonic() + 30
    while True:
        try:
            await client.workflow_service.describe_namespace(DescribeNamespaceRequest(namespace=namespace))
            return
        except RPCError:
            if time.monotonic() > deadline:
                raise
            await asyncio.sleep(0.5)


@pytest.fixture(scope="session")
async def temporal():
    address = get_settings().temporal_address
    if TEMPORAL_NAMESPACE != "default":
        await _ensure_namespace(address, TEMPORAL_NAMESPACE)
    return await Client.connect(address, namespace=TEMPORAL_NAMESPACE)


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


@pytest.fixture(scope="session")
async def skipping_env():
    """時間を飛ばせる Temporal の試験用サーバー（temporalio が初回に取ってくる）。送り直しの間隔（5秒・10秒）を待たない。"""
    env = await WorkflowEnvironment.start_time_skipping()
    yield env
    await env.shutdown()


class SkippingTemporal:
    """口（app.state.temporal）と作業者を、時間を飛ばせる Temporal に向けた間の道具。"""

    def __init__(self, env, workers: WorkerSet):
        self.env, self.workers = env, workers

    async def finished(self, job_id: str) -> None:
        """依頼の流れが終わるまで待つ。待っている間だけ、試験用サーバーは時間を飛ばす（状態を口で見て待つと飛ばない）。"""
        # get_workflow_handle の handle は自分では時間を飛ばさない（飛ばすのは start_workflow が返す handle だけ）
        try:
            async with self.env.time_skipping_unlocked():
                await self.env.client.get_workflow_handle(f"job-{job_id}").result()
        except WorkflowFailureError:
            pass  # 取り消した流れも「終わった」。どう終わったかは呼んだ試験が口で確かめる


@pytest.fixture
async def skipping(api, skipping_env):
    """Temporal 自身の送り直し（間隔 5秒・10秒）や待ちに頼る試験で使う。終わったら口を本物の Temporal に戻す。
    本物の Temporal（優先順位・公平さ・作業者の入れ替え）で確かめる試験は workers を使う。"""
    real = app.state.temporal
    ws = WorkerSet(skipping_env.client)
    await ws.start()
    app.state.temporal = skipping_env.client
    try:
        yield SkippingTemporal(skipping_env, ws)
    finally:
        app.state.temporal = real
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
