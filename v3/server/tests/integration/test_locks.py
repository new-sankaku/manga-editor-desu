"""ロック。"""

import uuid

from conftest import h, new_work, user

from v3server import lock_rules
from v3server.database_engine import get_sessionmaker
from v3server.request_actor import Actor


async def setup(api):
    a, b = user(), user()
    ids = await new_work(api, a)
    wid = ids["work"]
    await api.post(f"/works/{wid}/ops", headers=h(a), json={"type": "set_member", "user": b, "role": "assistant",
                                                             "granted": True})
    await api.post(f"/works/{wid}/ops", headers=h(a), json={"type": "assign_page", "page_id": ids["page1"],
                                                             "user": b, "assigned": True})
    pid = uuid.uuid4().hex
    r = await api.post(f"/works/{wid}/ops", headers=h(a), json={"type": "add_panel", "id": pid,
                                                                 "page_id": ids["page1"], "order": 1})
    assert r.status_code == 200
    return a, b, ids, pid


async def test_人のロックは他の人を止める(api):
    a, b, ids, pid = await setup(api)
    wid = ids["work"]
    r = await api.post(f"/works/{wid}/locks", headers=h(a), json={"target_kind": "panel", "target_id": pid,
                                                                   "reason": "下描き"})
    assert r.status_code == 201, r.text
    lock_id = r.json()["id"]

    assert (await api.post(f"/works/{wid}/ops", headers=h(b), json={"type": "update_panel", "id": pid,
                                                                     "role": "決め"})).status_code == 409
    # コマを取られているとき、そのページ全体も取れない
    assert (await api.post(f"/works/{wid}/locks", headers=h(b), json={"target_kind": "page",
                                                                       "target_id": ids["page1"],
                                                                       "reason": "x"})).status_code == 409
    # 持ち主は書ける
    assert (await api.post(f"/works/{wid}/ops", headers=h(a), json={"type": "update_panel", "id": pid,
                                                                     "role": "決め"})).status_code == 200
    # 他の人は外せない。持ち主は外せる
    assert (await api.delete(f"/works/{wid}/locks/{lock_id}", headers=h(b))).status_code == 403
    assert (await api.delete(f"/works/{wid}/locks/{lock_id}", headers=h(a))).status_code == 204
    assert (await api.post(f"/works/{wid}/ops", headers=h(b), json={"type": "update_panel", "id": pid,
                                                                     "role": "つなぎ"})).status_code == 200


async def test_ページを抜く操作はページの中のロックにも当たる(api):
    a, b, ids, pid = await setup(api)
    wid = ids["work"]
    assert (await api.post(f"/works/{wid}/locks", headers=h(b), json={"target_kind": "panel", "target_id": pid,
                                                                       "reason": "仕上げ"})).status_code == 201
    r = await api.post(f"/works/{wid}/ops", headers=h(a), json={"type": "set_removed", "target_kind": "page",
                                                                 "id": ids["page1"], "removed": True})
    assert r.status_code == 409


async def test_人はAIのロックを取り返せる(api, authz):
    a, b, ids, pid = await setup(api)
    wid = ids["work"]
    ai = Actor(kind="ai", id="job-x", on_behalf_of=a)
    async with get_sessionmaker()() as session:
        await lock_rules.acquire(session, authz, ai, wid, "page", ids["page1"], "作画", job_id="job-x")

    # AIのロック中は人の操作も止まる
    assert (await api.post(f"/works/{wid}/ops", headers=h(b), json={"type": "update_panel", "id": pid,
                                                                     "role": "決め"})).status_code == 409
    r = await api.post(f"/works/{wid}/locks", headers=h(b), json={"target_kind": "panel", "target_id": pid,
                                                                   "reason": "手で直す"})
    assert r.status_code == 201, r.text
    assert r.json()["preempted_job_ids"] == ["job-x"]
    events = (await api.get(f"/works/{wid}/events", headers=h(a))).json()
    assert "lock_preempted" in [e["op_type"] for e in events]

    # AIは人のロックを取り返せない
    async with get_sessionmaker()() as session:
        try:
            await lock_rules.acquire(session, authz, ai, wid, "panel", pid, "作画")
            raise AssertionError("取れてはいけない")
        except Exception as e:
            assert type(e).__name__ == "Locked"
