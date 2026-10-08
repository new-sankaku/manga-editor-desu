"""正本・操作の窓口・取り消し・権限。"""

import asyncio
import uuid

from conftest import h, new_work, user


async def op(api, wid, u, body):
    return await api.post(f"/works/{wid}/ops", headers=h(u), json=body)


async def panel_of(api, wid, u, panel_id):
    work = (await api.get(f"/works/{wid}", headers=h(u))).json()
    return next(p for p in work["panels"] if p["id"] == panel_id)


async def test_作品を作った人が作者になり出来事が順に積まれる(api):
    a = user()
    ids = await new_work(api, a)
    members = (await api.get(f"/works/{ids['work']}/members", headers=h(a))).json()
    assert members == [{"user": a, "role": "author"}]
    events = (await api.get(f"/works/{ids['work']}/events", headers=h(a))).json()
    assert [e["seq"] for e in events] == [1, 2, 3, 4, 5]
    assert [e["op_type"] for e in events] == ["create_work", "add_volume", "add_episode", "add_page", "add_page"]


async def test_取り消しと取り消しの取り消し(api):
    a = user()
    ids = await new_work(api, a)
    wid, pid = ids["work"], uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "add_panel", "id": pid, "page_id": ids["page1"], "order": 1,
                                    "content": {"place": "教室"}})).status_code == 200
    r = await op(api, wid, a, {"type": "update_panel", "id": pid, "content": {"place": "屋上"}})
    upd = r.json()["event_id"]

    r = await api.post(f"/works/{wid}/events/{upd}/undo", headers=h(a))
    assert r.status_code == 200, r.text
    assert (await panel_of(api, wid, a, pid))["content"] == {"place": "教室"}

    # 同じ出来事は2回取り消せない
    assert (await api.post(f"/works/{wid}/events/{upd}/undo", headers=h(a))).status_code == 409

    # 取り消しの取り消しで、やり直しになる
    r = await api.post(f"/works/{wid}/events/{r.json()['event_id']}/undo", headers=h(a))
    assert r.status_code == 200, r.text
    assert (await panel_of(api, wid, a, pid))["content"] == {"place": "屋上"}


async def _two_people_on_one_panel(api):
    a, b = user(), user()
    ids = await new_work(api, a)
    wid, pid = ids["work"], uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "set_member", "user": b, "role": "author", "granted": True})).status_code == 200
    assert (await op(api, wid, a, {"type": "add_panel", "id": pid, "page_id": ids["page1"], "order": 1,
                                    "content": {"place": "教室"}})).status_code == 200
    r = await op(api, wid, a, {"type": "update_panel", "id": pid, "content": {"place": "屋上"}})
    assert r.status_code == 200, r.text
    return a, b, wid, pid, r.json()["event_id"]


async def test_後で他の人が同じ項目を変えていたら取り消さず記録する(api):
    a, b, wid, pid, upd = await _two_people_on_one_panel(api)
    r = await op(api, wid, b, {"type": "update_panel", "id": pid, "content": {"place": "廊下"}})
    later = r.json()["event_id"]

    r = await api.post(f"/works/{wid}/events/{upd}/undo", headers=h(a))
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["code"] == "undo_conflict"
    [c] = body["conflicts"]
    assert (c["table"], c["id"], c["field"]) == ("panels", pid, "content")
    assert [e["event_id"] for e in c["events"]] == [later]
    assert c["events"][0]["actor_id"] == b
    # B さんの値は残る
    assert (await panel_of(api, wid, a, pid))["content"] == {"place": "廊下"}
    # 記録が残る
    recs = (await api.get(f"/works/{wid}/undo-conflicts", headers=h(a))).json()
    assert [(x["id"], x["event_id"]) for x in recs] == [(body["undo_conflict_id"], upd)]
    # 取り消していないので、後で B さんが自分の変更を取り消せば、A さんの取り消しは通る
    assert (await api.post(f"/works/{wid}/events/{later}/undo", headers=h(b))).status_code == 200
    r = await api.post(f"/works/{wid}/events/{upd}/undo", headers=h(a))
    assert r.status_code == 200, r.text
    assert (await panel_of(api, wid, a, pid))["content"] == {"place": "教室"}


async def test_後で他の人が別の項目を変えていても取り消せる(api):
    a, b, wid, pid, upd = await _two_people_on_one_panel(api)
    r = await op(api, wid, b, {"type": "update_panel", "id": pid, "role": "establishing"})
    assert r.status_code == 200, r.text

    r = await api.post(f"/works/{wid}/events/{upd}/undo", headers=h(a))
    assert r.status_code == 200, r.text
    panel = await panel_of(api, wid, a, pid)
    assert panel["content"] == {"place": "教室"}
    assert panel["role"] == "establishing"
    # B さんが付けた人の手の印は残る（取り消しで戻すのは、A さんの操作が付けた分だけ）
    assert "role" in panel["human_hand_fields"]


async def test_足した行を後で他の人が変えていたら取り消しで抜かない(api):
    a, b = user(), user()
    ids = await new_work(api, a)
    wid, pid = ids["work"], uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "set_member", "user": b, "role": "author", "granted": True})).status_code == 200
    add = (await op(api, wid, a, {"type": "add_panel", "id": pid, "page_id": ids["page1"], "order": 1})).json()
    assert (await op(api, wid, b, {"type": "update_panel", "id": pid, "content": {"place": "教室"}})).status_code == 200
    r = await api.post(f"/works/{wid}/events/{add['event_id']}/undo", headers=h(a))
    assert r.status_code == 409, r.text
    assert (await panel_of(api, wid, a, pid))["removed"] is False


async def test_追加の取り消しは消さずに抜く(api):
    a = user()
    ids = await new_work(api, a)
    wid, pid = ids["work"], uuid.uuid4().hex
    ev = (await op(api, wid, a, {"type": "add_panel", "id": pid, "page_id": ids["page1"], "order": 1})).json()
    assert (await api.post(f"/works/{wid}/events/{ev['event_id']}/undo", headers=h(a))).status_code == 200
    assert (await panel_of(api, wid, a, pid))["removed"] is True


async def test_権限_見るだけ_編集者_アシスタント(api):
    a, viewer, editor, asst = user(), user(), user(), user()
    ids = await new_work(api, a)
    wid = ids["work"]
    for u, role in [(viewer, "viewer"), (editor, "editor"), (asst, "assistant")]:
        assert (await op(api, wid, a, {"type": "set_member", "user": u, "role": role, "granted": True})).status_code == 200
    assert (await op(api, wid, a, {"type": "assign_page", "page_id": ids["page1"], "user": asst,
                                    "assigned": True})).status_code == 200

    panel = {"type": "add_panel", "page_id": ids["page1"], "order": 1}
    assert (await op(api, wid, viewer, panel)).status_code == 403
    assert (await op(api, wid, editor, panel)).status_code == 403
    assert (await op(api, wid, asst, panel)).status_code == 200
    # 割り当てられていないページには描けない
    assert (await op(api, wid, asst, {**panel, "page_id": ids["page2"]})).status_code == 403
    # 作品の設定は作者だけ
    assert (await op(api, wid, asst, {"type": "set_work_settings", "title": "x"})).status_code == 403
    # 招かれていない人は見ることもできない
    assert (await api.get(f"/works/{wid}", headers=h(user()))).status_code == 403


async def test_同時に書いても番号が飛ばず重ならない(api):
    a = user()
    ids = await new_work(api, a)
    wid = ids["work"]
    rs = await asyncio.gather(*[
        op(api, wid, a, {"type": "add_panel", "page_id": ids["page1"], "order": i}) for i in range(20)
    ])
    assert all(r.status_code == 200 for r in rs), [r.text for r in rs if r.status_code != 200]
    seqs = sorted(r.json()["seq"] for r in rs)
    assert seqs == list(range(6, 26))


async def test_閾値は出典と検証の状態を持つ(api):
    a = user()
    ids = await new_work(api, a)
    wid = ids["work"]
    bad = await op(api, wid, a, {"type": "set_threshold", "key": "panels_per_page.max", "value": {"v": 8}})
    assert bad.status_code == 422
    ev = (await op(api, wid, a, {"type": "set_threshold", "key": "panels_per_page.max", "value": {"v": 8},
                                  "source": "試験", "status": "unverified"})).json()
    work = (await api.get(f"/works/{wid}", headers=h(a))).json()
    assert work["thresholds"][0]["status"] == "unverified"
    assert (await api.post(f"/works/{wid}/events/{ev['event_id']}/undo", headers=h(a))).status_code == 200
    assert (await api.get(f"/works/{wid}", headers=h(a))).json()["thresholds"] == []


async def test_指摘への反応は記録として残し取り消さない(api):
    a = user()
    ids = await new_work(api, a)
    wid = ids["work"]
    ev = (await op(api, wid, a, {"type": "record_finding_reaction", "finding_key": "balloon_overlap",
                                  "target_kind": "page", "target_id": ids["page1"], "reaction": "disagreed"})).json()
    assert (await api.post(f"/works/{wid}/events/{ev['event_id']}/undo", headers=h(a))).status_code == 409
