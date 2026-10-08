"""知らせ（決めごと 17章）を、本物の Temporal・PostgreSQL と偽の ComfyUI・LLM・検出器で通す。
外への送り先は送り手（CHANNEL_SENDERS）を差し替えて受ける。"""

import pytest
from conftest import h, wait_for
from test_harness import (  # noqa: F401  (fixture)
    admin,
    comfy,
    harness,
    harness_temporal,
    make_work,
    no_leftover_flows,
    script,
    services,
    start,
    unit_post,
    until_unit,
)

from v3server.harness import harness_notify


@pytest.fixture
def sent(monkeypatch):
    got: list[tuple[str, dict]] = []

    async def fake(target, body, s):
        got.append((target, body))
    monkeypatch.setitem(harness_notify.CHANNEL_SENDERS, "webhook", fake)
    return got


async def _notes(api, w, **params):
    r = await api.get(f"/works/{w['wid']}/harness/notifications", headers=h(w["a"]), params=params)
    assert r.status_code == 200, r.text
    return r.json()["notifications"]


async def test_決まりが無ければアプリの中の一覧にだけ出し_外へは送らない(api, services, harness, script, sent):
    w = await make_work(api)
    await start(api, w)
    u = await until_unit(api, w, "awaiting_review")

    async def generated():
        ns = await _notes(api, w)
        return ns if any(n["kind"] == "generated" and n["unit_id"] == u["unit_id"] for n in ns) else None
    ns = await wait_for(generated, 30)
    assert all(n["deliveries"] == [] for n in ns) and sent == []
    nid = next(n["id"] for n in ns if n["kind"] == "generated")
    r = await api.post(f"/works/{w['wid']}/harness/notifications/{nid}/read", headers=h(w["a"]))
    assert r.status_code == 200 and r.json()["read_by"] == w["a"]
    assert nid not in [n["id"] for n in await _notes(api, w, unread=True)]


async def test_判断待ちが長いと上げて全部の送り先へ送る(api, services, harness, script, sent):
    w = await make_work(api)
    r = await api.put(f"/works/{w['wid']}/harness/notification-settings", headers=h(w["a"]), json={
        "kinds": ["generated", "review_overdue"], "escalate_after_notices": 2,
        "webhooks": [{"url": "https://hooks.example.test/a", "kinds": ["generated"], "secret": "s"}]})
    assert r.status_code == 200, r.text
    r = await api.get(f"/works/{w['wid']}/harness/notification-settings", headers=h(w["a"]))
    assert r.json()["settings"]["webhooks"] == [{"url": "https://hooks.example.test/a", "kinds": ["generated"],
                                                 "signed": True}]
    # 判断待ちの知らせの間を短くする（作業の上限で決める。決まった秒は待たず、知らせが届くまで見る）
    await start(api, w, unit={"review_notice_seconds": 1})
    u = await until_unit(api, w, "awaiting_review")

    async def escalated():
        ns = await _notes(api, w)
        return ns if any(n["level"] == "escalated" for n in ns) else None
    ns = await wait_for(escalated, 30)
    over = [n for n in ns if n["kind"] == "review_overdue"]
    assert [n["level"] for n in sorted(over, key=lambda n: n["created_at"])][:2] == ["warn", "escalated"]

    async def delivered():
        kinds = sorted({b["kind"] + ":" + b["level"] for _, b in sent})
        return kinds if "review_overdue:escalated" in kinds and "generated:info" in kinds else None
    kinds = await wait_for(delivered, 30)
    # 送り先の種類の絞り込み（generated だけ）は、上げた知らせには効かない。上げる前の review_overdue は送らない
    assert "review_overdue:warn" not in kinds
    assert all(t == "https://hooks.example.test/a" for t, _ in sent)
    r = await unit_post(api, w, u["unit_id"], "control", {"action": "cancel_unit"})
    assert r.status_code == 200, r.text


async def test_知らない種類の決まりは断る(api, services, harness, script):
    w = await make_work(api, thresholds=False)
    r = await api.put(f"/works/{w['wid']}/harness/notification-settings", headers=h(w["a"]),
                      json={"kinds": ["mail"]})
    assert r.status_code == 422
