"""順番待ち・送り先の制限・失敗の扱い。Temporal を実際に使う。"""

import asyncio
import uuid
from datetime import timedelta

import pytest
from temporalio.client import WorkflowExecutionStatus
from conftest import h, new_work, user, wait_for

from v3server.admin_command_line import grant_admin
from v3server.database_engine import get_sessionmaker
from v3server.generation_queue import job_start_and_control
from v3server.request_actor import Actor

ADMIN = "admin-" + uuid.uuid4().hex[:6]


@pytest.fixture(scope="module")
async def admin():
    await grant_admin(ADMIN, revoke=False)
    return ADMIN


async def make_service(api, admin, *, location="local", send_mode="serial", n=1, budget=None):
    name = f"svc-{uuid.uuid4().hex[:6]}"
    process = f"proc-{uuid.uuid4().hex[:6]}"
    r = await api.post("/services", headers=h(admin), json={
        "name": name, "kind": "text", "location": location, "adapter": "litellm", "send_mode": send_mode,
        "max_concurrency": n, "monthly_budget": budget})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    r = await api.put(f"/services/{sid}/processes/{process}", headers=h(admin),
                      json={"model": "fake", "cost_per_call": 10})
    assert r.status_code == 200, r.text
    r = await api.put(f"/routes/{process}", headers=h(admin),
                      json={"service_id": sid, "resend_limit": 2, "regenerate_limit": 0, "ai_task": "name",
                            "ai_action": "propose"})
    assert r.status_code == 200, r.text
    return sid, process


async def job(api, wid, u, jid):
    jobs = (await api.get(f"/works/{wid}/jobs", headers=h(u))).json()
    return next(j for j in jobs if j["id"] == jid)


async def until_status(api, wid, u, jid, *statuses, timeout=40):
    async def check():
        j = await job(api, wid, u, jid)
        return j if j["status"] in statuses else None
    return await wait_for(check, timeout)


async def enqueue(api, wid, u, process, **request):
    r = await api.post(f"/works/{wid}/jobs", headers=h(u), json={"process": process, "request": request})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_管理者でなければつなぎ先を変えられない(api):
    r = await api.post("/services", headers=h(user()), json={
        "name": "x", "kind": "text", "location": "local", "adapter": "litellm", "send_mode": "serial"})
    assert r.status_code == 403


async def test_1件ずつと同時にN件まで(api, admin, workers, fake_adapter):
    a = user()
    wid = (await new_work(api, a))["work"]
    serial_sid, serial_p = await make_service(api, admin, send_mode="serial")
    par_sid, par_p = await make_service(api, admin, send_mode="parallel", n=3)
    await workers.reload()

    ids = [await enqueue(api, wid, a, serial_p, tag=f"s{i}", sleep=0.5) for i in range(3)]
    for jid in ids:
        await until_status(api, wid, a, jid, "done")
    assert fake_adapter["max_running"] == 1

    fake_adapter["max_running"] = 0
    ids = [await enqueue(api, wid, a, par_p, tag=f"p{i}", sleep=1.5) for i in range(6)]
    for jid in ids:
        await until_status(api, wid, a, jid, "done")
    assert fake_adapter["max_running"] == 3


async def test_APIの先は送ってよい先に無ければ頼めない(api, admin, workers, fake_adapter):
    a = user()
    wid = (await new_work(api, a))["work"]
    sid, p = await make_service(api, admin, location="api")
    await workers.reload()

    r = await api.post(f"/works/{wid}/jobs", headers=h(a), json={"process": p, "request": {"tag": "x"}})
    assert r.status_code == 403
    assert (await api.post(f"/works/{wid}/ops", headers=h(a), json={
        "type": "allow_destination", "service_id": sid, "allowed": True})).status_code == 200
    jid = await enqueue(api, wid, a, p, tag="allowed")
    assert (await until_status(api, wid, a, jid, "done"))["result"] == {"text": "ok:allowed"}


async def test_待っている間に送ってよい先から外されたら送らない(api, admin, workers, fake_adapter):
    a = user()
    wid = (await new_work(api, a))["work"]
    sid, p = await make_service(api, admin, location="api")
    await api.patch(f"/services/{sid}", headers=h(admin), json={"paused": True})
    await workers.reload()
    await api.post(f"/works/{wid}/ops", headers=h(a), json={
        "type": "allow_destination", "service_id": sid, "allowed": True})
    jid = await enqueue(api, wid, a, p, tag="revoked")
    await api.post(f"/works/{wid}/ops", headers=h(a), json={
        "type": "allow_destination", "service_id": sid, "allowed": False})
    await api.patch(f"/services/{sid}", headers=h(admin), json={"paused": False})
    await workers.reload()

    j = await until_status(api, wid, a, jid, "stopped")
    assert j["failure_kind"] == "destination_not_allowed"
    assert ("revoked" not in [tag for _, tag in fake_adapter["calls"]])


async def test_休ませた先は待ちに残り戻すと送る(api, admin, workers, fake_adapter):
    a = user()
    wid = (await new_work(api, a))["work"]
    sid, p = await make_service(api, admin)
    await api.patch(f"/services/{sid}", headers=h(admin), json={"paused": True})
    await workers.reload()
    jid = await enqueue(api, wid, a, p, tag="paused")
    await asyncio.sleep(2)
    assert (await job(api, wid, a, jid))["status"] == "queued"
    await api.patch(f"/services/{sid}", headers=h(admin), json={"paused": False})
    await workers.reload()
    await until_status(api, wid, a, jid, "done")


async def test_失敗の種類ごとの扱い(api, admin, workers, fake_adapter):
    a = user()
    wid = (await new_work(api, a))["work"]
    sid, p = await make_service(api, admin)
    await workers.reload()

    def count(tag):
        return sum(1 for _, t in fake_adapter["calls"] if t == tag)

    # 断られたら送り直さない
    jid = await enqueue(api, wid, a, p, tag="refused", script=["refused"])
    assert (await until_status(api, wid, a, jid, "stopped"))["failure_kind"] == "refused"
    assert count("refused") == 1

    # 通信の失敗は resend_limit（2）回まで送り直す。3回目で通る
    jid = await enqueue(api, wid, a, p, tag="flaky", script=["transport", "transport", "ok"])
    await until_status(api, wid, a, jid, "done", timeout=60)
    assert count("flaky") == 3

    # 回数を超えたら止める
    jid = await enqueue(api, wid, a, p, tag="down", script=["transport"] * 5)
    assert (await until_status(api, wid, a, jid, "stopped", timeout=60))["failure_kind"] == "transport"
    assert count("down") == 3

    # 制限に当たったら待って同じ先に送り直す。回数には数えない
    jid = await enqueue(api, wid, a, p, tag="limited", script=["rate_limited"] * 3 + ["ok"])
    await until_status(api, wid, a, jid, "waiting_limit")
    await until_status(api, wid, a, jid, "done", timeout=60)
    assert count("limited") == 4

    # 止まったものの「もう一度」
    r = await api.post(f"/works/{wid}/jobs/{(await job(api, wid, a, jid))['id']}/retry", headers=h(a))
    assert r.status_code == 422


async def test_取り消すと止まる(api, admin, workers, fake_adapter):
    a = user()
    wid = (await new_work(api, a))["work"]
    sid, p = await make_service(api, admin)
    await workers.reload()
    jid = await enqueue(api, wid, a, p, tag="long", sleep=30)
    await until_status(api, wid, a, jid, "running")
    assert (await api.post(f"/works/{wid}/jobs/{jid}/cancel", headers=h(a))).status_code == 202
    await until_status(api, wid, a, jid, "cancelled", timeout=20)


async def test_予算の上限で待ち_続けるで再開する(api, admin, workers, fake_adapter):
    a = user()
    wid = (await new_work(api, a))["work"]
    sid, p = await make_service(api, admin, budget=10)
    await workers.reload()
    first = await enqueue(api, wid, a, p, tag="b1")
    await until_status(api, wid, a, first, "done")
    second = await enqueue(api, wid, a, p, tag="b2")
    assert (await until_status(api, wid, a, second, "waiting_budget"))["failure_kind"] == "budget"
    await api.patch(f"/services/{sid}", headers=h(admin), json={"monthly_budget": 100})
    assert (await api.post(f"/works/{wid}/jobs/{second}/resume", headers=h(a))).status_code == 202
    await until_status(api, wid, a, second, "done")


async def test_人の依頼をAIの依頼より先に送る(api, admin, workers, fake_adapter, authz, temporal):
    """Temporal の優先順位（priority_key）が待ち行列で効くかを確かめる。"""

    a = user()
    wid = (await new_work(api, a))["work"]
    sid, p = await make_service(api, admin)
    await api.patch(f"/services/{sid}", headers=h(admin), json={"paused": True})
    await workers.reload()

    # 依頼を受ける口は、送信を待ち行列に入れ終えてから返す（job_start_and_control.enqueue）。
    # ここまでで6件とも待ち行列に入っている
    ai = Actor(kind="ai", id="ai-test", on_behalf_of=a)
    async with get_sessionmaker()() as session:
        for i in range(3):
            await job_start_and_control.enqueue(session, authz, temporal, ai, wid, p, {"tag": f"ai{i}"}, "ai")
    for i in range(3):
        await enqueue(api, wid, a, p, tag=f"human{i}")

    await api.patch(f"/services/{sid}", headers=h(admin), json={"paused": False})
    await workers.reload()
    await wait_for(lambda: _done_count(fake_adapter, 6), 40)
    order = [t for _, t in fake_adapter["calls"] if t and (t.startswith("ai") or t.startswith("human"))]
    assert order[:3] == ["human0", "human1", "human2"], order


async def _done_count(state, n):
    return sum(1 for _, t in state["calls"] if t and (t.startswith("ai") or t.startswith("human"))) >= n


async def test_同じ優先順位の中では作品ごとに順に送る(api, admin, workers, fake_adapter):
    """Temporal の公平さの鍵（fairness_key=作品ID）。先に多く頼んだ作品が、後の作品を待たせないか。"""

    a = user()
    w1 = (await new_work(api, a))["work"]
    w2 = (await new_work(api, a))["work"]
    sid, p = await make_service(api, admin)
    await api.patch(f"/services/{sid}", headers=h(admin), json={"paused": True})
    await workers.reload()
    for i in range(8):
        await enqueue(api, w1, a, p, tag=f"fairA{i}")
    for i in range(3):
        await enqueue(api, w2, a, p, tag=f"fairB{i}")

    await api.patch(f"/services/{sid}", headers=h(admin), json={"paused": False})
    await workers.reload()

    async def done():
        return sum(1 for _, t in fake_adapter["calls"] if t and t.startswith("fair")) >= 11

    await wait_for(done, 40)
    order = [t for _, t in fake_adapter["calls"] if t and t.startswith("fair")]
    b_pos = [i + 1 for i, t in enumerate(order) if t.startswith("fairB")]
    # 公平さが無ければ B は 9〜11 番目。作品ごとに回れば、最初の6件の中に B が3件とも入る
    assert b_pos[-1] <= 6, order


async def test_待ち行列に入れられなければ依頼を止めて知らせる(api, admin, workers, fake_adapter, temporal, monkeypatch):
    """制御の作業者が動いていないとき。依頼を受けた（201）と返さず、依頼を止めて 503 で知らせる。"""

    a = user()
    wid = (await new_work(api, a))["work"]
    _, p = await make_service(api, admin)
    # 作業者のいない制御の待ち行列へ流す
    monkeypatch.setattr(job_start_and_control, "CONTROL_QUEUE", f"v3-control-nobody-{uuid.uuid4().hex[:6]}")
    monkeypatch.setattr(job_start_and_control, "QUEUE_ENTRY_WAIT", timedelta(seconds=2))
    r = await api.post(f"/works/{wid}/jobs", headers=h(a), json={"process": p, "request": {"tag": "nobody"}})
    assert r.status_code == 503 and r.json()["code"] == "queue_not_running", r.text
    (j,) = (await api.get(f"/works/{wid}/jobs", headers=h(a))).json()
    assert (j["status"], j["failure_kind"]) == ("stopped", "queue_not_running")
    desc = await temporal.get_workflow_handle(job_start_and_control.workflow_id(j["id"])).describe()
    assert desc.status == WorkflowExecutionStatus.TERMINATED
