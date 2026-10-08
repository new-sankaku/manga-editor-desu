"""作品をまたぐ画面が要る口（V3画面の一覧 5章）。PostgreSQL・OpenFGA・Temporal を実際に使う。
つなぎ先の様子を読む口（ComfyUI・LiteLLM）は、この環境に本物が無いので、口を呼ぶ所（service_inspection._client）を
模擬（mock）の答えに差し替えて確かめる。本物の ComfyUI・LiteLLM への呼び出しは未検証。"""

import json

import httpx
import pytest
from conftest import h, new_work, user, wait_for
from test_human_ai_interchange import TERMS, op, work_json
from test_human_edit_and_handover import image_dir  # noqa: F401  (fixture)
from test_human_tools_and_finishing import export_env, ready_page  # noqa: F401  (export_env は fixture)
from test_queue import admin, make_service  # noqa: F401  (admin は fixture)

from v3server.service_senders import service_inspection


def live(rows, **kw):
    return [r for r in rows if not r.get("removed") and all(r[k] == v for k, v in kw.items())]


# ---------------------------------------------------------------- 1. ページの割り当ての一覧


async def test_ページの割り当ての一覧(api):
    a, b, c = user(), user(), user()
    ids = await new_work(api, a)
    wid = ids["work"]
    for u in (b, c):
        assert (await op(api, wid, a, {"type": "set_member", "user": u, "role": "assistant", "granted": True})).status_code == 200
    assert (await op(api, wid, a, {"type": "assign_page", "page_id": ids["page1"], "user": b, "assigned": True})).status_code == 200
    assert (await op(api, wid, a, {"type": "assign_page", "page_id": ids["page1"], "user": c, "assigned": True})).status_code == 200
    assert (await op(api, wid, a, {"type": "assign_page", "page_id": ids["page2"], "user": c, "assigned": True})).status_code == 200
    assert (await op(api, wid, a, {"type": "assign_page", "page_id": ids["page2"], "user": c, "assigned": False})).status_code == 200
    r = await api.get(f"/works/{wid}/page-assignments", headers=h(b))
    assert r.status_code == 200, r.text
    got = {p["page_id"]: p["users"] for p in r.json()}
    assert got == {ids["page1"]: sorted([b, c]), ids["page2"]: []}
    assert (await api.get(f"/works/{wid}/page-assignments", headers=h(user()))).status_code == 403


# ---------------------------------------------------------------- 2・3. 話ごとの構成・伏線と、前の話から引き継ぐ


async def test_話ごとの構成と伏線_前の話から人物と生成の中身を引き継ぐ(api):
    a, ed = user(), user()
    ids = await new_work(api, a)
    wid = ids["work"]
    assert (await op(api, wid, a, {"type": "set_member", "user": ed, "role": "editor", "granted": True})).status_code == 200
    ep2 = "e2" + ids["episode"][2:]
    assert (await op(api, wid, a, {"type": "add_episode", "id": ep2, "volume_id": ids["volume"], "number": 2})).status_code == 200
    hero, gone = "m1" + ids["work"][2:], "m2" + ids["work"][2:]
    for mid, name in ((hero, "主人公"), (gone, "脇役")):
        assert (await op(api, wid, a, {"type": "add_material_entry", "id": mid, "kind": "character", "name": name})).status_code == 200
    gen = {"prompt": "夕方の光", "loras": [{"name": "style", "weight": 0.6}]}
    r = await op(api, wid, a, {"type": "set_episode_plan", "episode_id": ids["episode"], "synopsis": "出会い",
                               "cast_entry_ids": [hero, gone], "generation_defaults": gen})
    assert r.status_code == 200, r.text
    # 編集者は構成を変えられない（作者だけ）
    assert (await op(api, wid, ed, {"type": "set_episode_plan", "episode_id": ids["episode"], "notes": "x"})).status_code == 403
    # 形の違う生成の中身・採っていない設定資料は止める
    assert (await op(api, wid, a, {"type": "set_episode_plan", "episode_id": ids["episode"],
                                   "generation_defaults": {"seed": "x"}})).status_code == 422
    # 伏線：1話で張って、2話で回収する
    fid = "f1" + ids["work"][2:]
    assert (await op(api, wid, a, {"type": "add_foreshadowing", "id": fid, "planted_episode_id": ids["episode"],
                                   "text": "古い鍵"})).status_code == 200
    assert (await op(api, wid, a, {"type": "update_foreshadowing", "id": fid, "payoff_episode_id": ep2,
                                   "state": "paid_off"})).status_code == 200

    # 引き継ぐ前に、脇役を抜く（抜いた設定資料は写さない）
    assert (await op(api, wid, a, {"type": "set_removed", "target_kind": "material_entry", "id": gone, "removed": True})).status_code == 200
    r = await op(api, wid, a, {"type": "carry_over_episode_plan", "episode_id": ep2})
    assert r.status_code == 200, r.text
    carry_event = r.json()["event_id"]
    w = await work_json(api, wid, a)
    plans = {p["episode_id"]: p for p in w["episode_plans"]}
    assert plans[ep2]["cast_entry_ids"] == [hero] and plans[ep2]["generation_defaults"]["prompt"] == "夕方の光"
    assert plans[ep2]["carried_from_episode_id"] == ids["episode"]
    # 構成（あらすじ）は引き継がない
    assert plans[ep2]["synopsis"] is None and plans[ids["episode"]]["synopsis"] == "出会い"
    assert "cast_entry_ids" in plans[ep2]["human_hand_fields"]
    (f,) = w["foreshadowings"]
    assert f["payoff_episode_id"] == ep2 and f["state"] == "paid_off" and "state" in f["human_hand_fields"]

    # 最初の話には前の話が無い
    r = await op(api, wid, a, {"type": "carry_over_episode_plan", "episode_id": ids["episode"]})
    assert r.status_code == 422 and "前の話" in r.text
    # 引き継ぎは1回で取り消せる
    r = await api.post(f"/works/{wid}/events/{carry_event}/undo", headers=h(a))
    assert r.status_code == 200, r.text
    plans = {p["episode_id"]: p for p in (await work_json(api, wid, a))["episode_plans"]}
    assert plans[ep2]["cast_entry_ids"] == [] and plans[ep2]["carried_from_episode_id"] is None
    # 伏線を抜く・戻す
    assert (await op(api, wid, a, {"type": "set_removed", "target_kind": "foreshadowing", "id": fid, "removed": True})).status_code == 200
    assert (await work_json(api, wid, a))["foreshadowings"][0]["removed"] is True


# ---------------------------------------------------------------- 4・11. 書き出しの進み具合と、ページの下見の絵


@pytest.mark.full
async def test_書き出しの進み具合をページごとに残す(api, workers, export_env):  # noqa: F811
    a = user()
    ids, _p, _t = await ready_page(api, a)
    wid = ids["work"]
    r = await api.post(f"/works/{wid}/exports", headers=h(a), json={"format": "png", "page_ids": [ids["page1"]], "dpi": 72})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["done_page_ids"] == []

    async def done():
        x = (await api.get(f"/works/{wid}/exports/{run['id']}", headers=h(a))).json()
        return x if x["status"] in ("done", "failed") else None

    out = await wait_for(done, 60)
    assert out["status"] == "done", out["detail"]
    assert out["done_page_ids"] == [ids["page1"]]


@pytest.mark.full
async def test_ページの下見の絵は控え_中身が変わると描き直す(api, export_env):  # noqa: F811
    a = user()
    ids, p, t = await ready_page(api, a)
    wid = ids["work"]
    url = f"/works/{wid}/pages/{ids['page1']}/preview?size=256"
    r1 = await api.get(url, headers=h(a))
    assert r1.status_code == 200, r1.text
    assert r1.headers["content-type"] == "image/png" and r1.headers["x-v3-preview-cache"] == "miss"
    from io import BytesIO

    from PIL import Image
    img = Image.open(BytesIO(r1.content))
    assert max(img.size) == 256
    r2 = await api.get(url, headers=h(a))
    assert r2.headers["x-v3-preview-cache"] == "hit" and r2.content == r1.content
    # 文字を動かすと描き直す
    assert (await op(api, wid, a, {"type": "update_text_item", "id": t["id"], "text": "いう"})).status_code == 200
    r3 = await api.get(url, headers=h(a))
    assert r3.headers["x-v3-preview-cache"] == "miss" and r3.content != r1.content
    # 見られない人は読めない。寸法の無い作品は理由を返す
    assert (await api.get(url, headers=h(user()))).status_code == 403
    b = user()
    other = await new_work(api, b)
    r = await api.get(f"/works/{other['work']}/pages/{other['page1']}/preview?size=256", headers=h(b))
    assert r.status_code == 422 and "page_spec" in r.text


# ---------------------------------------------------------------- 5・6. 処理の中身の一部を直す・送り先の無い処理の作業と手


async def test_処理の中身の一部だけ直す_手順は送らなければ残る(api, admin):  # noqa: F811
    sid, process = await make_service(api, admin)
    wf = {"1": {"class_type": "KSampler", "inputs": {}}}
    r = await api.put(f"/services/{sid}/processes/{process}", headers=h(admin),
                      json={"model": "m1", "cost_per_call": 3, "comfy_workflow": wf})
    assert r.status_code == 200
    r = await api.patch(f"/services/{sid}/processes/{process}", headers=h(admin), json={"aptitude": "good"})
    assert r.status_code == 200, r.text
    assert r.json()["comfy_workflow"] == wf and r.json()["model"] == "m1" and r.json()["aptitude"] == "good"
    full = (await api.get("/services", headers=h(admin))).json()
    sp = next(x for x in full["processes"] if x["service_id"] == sid and x["process"] == process)
    assert sp["comfy_workflow"] == wf
    # 送った null は空にする。変える項目が無い・無い処理は断る。管理者でなければ断る
    r = await api.patch(f"/services/{sid}/processes/{process}", headers=h(admin), json={"comfy_workflow": None})
    assert r.status_code == 200 and r.json()["comfy_workflow"] is None and r.json()["model"] == "m1"
    assert (await api.patch(f"/services/{sid}/processes/{process}", headers=h(admin), json={})).status_code == 422
    assert (await api.patch(f"/services/{sid}/processes/nothing", headers=h(admin), json={"model": "x"})).status_code == 404
    assert (await api.patch(f"/services/{sid}/processes/{process}", headers=h(user()), json={"model": "x"})).status_code == 403
    # 画像生成の処理でない処理に生成の中身は入れられない
    r = await api.patch(f"/services/{sid}/processes/{process}", headers=h(admin), json={"comfy_graph_settings": {}})
    assert r.status_code == 422


async def test_送り先の無い処理も作業と手を返す(api):
    r = await api.get("/known-processes", headers=h(user()))
    assert r.status_code == 200
    rows = {x["process"]: x for x in r.json()}
    assert rows["extract_characters"]["ai_task"] == "settings_material" and rows["extract_characters"]["ai_action"] == "propose"
    assert all(set(x) == {"process", "ai_task", "ai_action", "routed"} for x in rows.values())


# ---------------------------------------------------------------- 7. つなぎ先の様子（模擬の ComfyUI・LiteLLM）


def _mock_comfy(request: httpx.Request) -> httpx.Response:
    """模擬の ComfyUI。本物の答えの形（/system_stats・/queue・/object_info）に合わせた小さな答え。"""
    if request.url.path == "/system_stats":
        return httpx.Response(200, json={"system": {"comfyui_version": "0.3.x", "python_version": "3.12"},
                                         "devices": [{"name": "cpu", "type": "cpu", "vram_total": 0}]})
    if request.url.path == "/queue":
        return httpx.Response(200, json={"queue_running": [[0, "p1", {}, {}, []]],
                                         "queue_pending": [[1, "p2", {}, {}, []], [2, "p3", {}, {}, []]]})
    if request.url.path == "/object_info":
        return httpx.Response(200, json={
            "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["a.safetensors", "b.safetensors"]]}}},
            "LoraLoader": {"input": {"required": {"lora_name": ["COMBO", {"options": ["x.safetensors"]}],
                                                  "strength_model": ["FLOAT", {}]}}},
            "KSampler": {"input": {"required": {"sampler_name": [["euler"]], "steps": ["INT", {}]}}}})
    return httpx.Response(404)


def _mock_litellm(request: httpx.Request) -> httpx.Response:
    """模擬の LiteLLM（/v1/models）。鍵が無ければ 401。"""
    if not request.headers.get("authorization", "").startswith("Bearer "):
        return httpx.Response(401)
    return httpx.Response(200, json={"object": "list", "data": [{"id": "gpt-x"}, {"id": "claude-y"}]})


@pytest.fixture
def mock_services(monkeypatch):
    def client(base_url, headers=None):
        handler = _mock_litellm if "litellm" in base_url or "54000" in base_url else _mock_comfy
        if "unreachable" in base_url:
            def handler(request):
                raise httpx.ConnectError("つながらない（模擬）", request=request)
        return httpx.AsyncClient(base_url=base_url, headers=headers or {}, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(service_inspection, "_client", client)
    from v3server.server_settings import get_settings
    monkeypatch.setattr(get_settings(), "litellm_url", "http://litellm.mock:54000")
    monkeypatch.setattr(get_settings(), "litellm_master_key", "sk-mock")


async def test_つなぎ先を試す_走り具合_止まったもの_入っているモデル(api, admin, mock_services):  # noqa: F811
    sid, _ = await make_service(api, admin)  # ComfyUI（http://127.0.0.1:8188。答えは模擬）
    r = await api.post(f"/services/{sid}/connection-test", headers=h(admin))
    assert r.status_code == 200 and r.json()["ok"] and r.json()["state"] == "connected", r.text
    assert r.json()["result"]["system"]["comfyui_version"] == "0.3.x"
    st = (await api.get(f"/services/{sid}/status", headers=h(admin))).json()
    assert st["remote"] == {"ok": True, "running": 1, "pending": 2} and st["stopped_jobs"] == []
    m = (await api.get(f"/services/{sid}/models", headers=h(admin))).json()
    assert m["models"] == {"ckpt_name": ["a.safetensors", "b.safetensors"], "lora_name": ["x.safetensors"],
                           "sampler_name": ["euler"]}
    assert m["system_stats"]["devices"][0]["name"] == "cpu"
    # LiteLLM
    lid, _ = await make_service(api, admin, location="api")
    assert (await api.get(f"/services/{lid}/models", headers=h(admin))).json()["models"] == {"model": ["claude-y", "gpt-x"]}
    st = (await api.get(f"/services/{lid}/status", headers=h(admin))).json()
    assert st["remote"]["ok"] and st["remote"]["running"] is None
    # つながらない先は state=stopped にして理由を返す
    r = await api.patch(f"/services/{sid}", headers=h(admin), json={"endpoint": "http://127.0.0.1:1/unreachable"})
    assert r.status_code == 200, r.text
    r = (await api.post(f"/services/{sid}/connection-test", headers=h(admin))).json()
    assert not r["ok"] and r["state"] == "stopped" and "つながらない" in r["detail"]
    assert (await api.post(f"/services/{sid}/connection-test", headers=h(user()))).status_code == 403


# ---------------------------------------------------------------- 8. 組を残す・同じ指示で比べる


@pytest.mark.full
async def test_組を残して当てる_同じ指示で比べる(api, admin, workers, fake_adapter):  # noqa: F811
    a = user()
    wid = (await new_work(api, a))["work"]
    s1, process = await make_service(api, admin)
    s2, _ = await make_service(api, admin)
    assert (await api.put(f"/services/{s2}/processes/{process}", headers=h(admin), json={"model": "fake"})).status_code == 200
    name = f"組-{s1[:6]}"
    r = await api.post("/service-sets", headers=h(admin), json={"name": name, "routes": {process: s2}})
    assert r.status_code == 201, r.text
    set_id = r.json()["id"]
    assert (await api.post("/service-sets", headers=h(admin), json={"name": name, "routes": {process: s2}})).status_code == 422
    assert (await api.post("/service-sets", headers=h(admin), json={"name": "x", "routes": {"no-such": s2}})).status_code == 422
    r = await api.post(f"/service-sets/{set_id}/apply", headers=h(admin))
    assert r.status_code == 200 and r.json()["changed"] == [{"process": process, "from": s1, "to": s2}]
    routes = (await api.get("/services", headers=h(admin))).json()["routes"]
    assert next(x for x in routes if x["process"] == process)["service_id"] == s2
    assert any(s["id"] == set_id for s in (await api.get("/service-sets", headers=h(admin))).json())
    assert (await api.get("/service-sets", headers=h(a))).status_code == 403

    await workers.reload()
    r = await api.post(f"/works/{wid}/service-comparisons", headers=h(a),
                       json={"process": process, "request": {"tag": "cmp"}, "service_ids": [s1, s2]})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert [j["service_id"] for j in r.json()["jobs"]] == [s1, s2]

    async def finished():
        c = (await api.get(f"/works/{wid}/service-comparisons/{cid}", headers=h(a))).json()
        return c if all(j["status"] == "done" for j in c["results"]) else None

    c = await wait_for(finished, 40)
    assert [j["service_id"] for j in c["results"]] == [s1, s2]
    assert all(j["result"] for j in c["results"])
    assert (await api.get(f"/works/{wid}/service-comparisons", headers=h(a))).json()[0]["id"] == cid
    assert (await api.delete(f"/service-sets/{set_id}", headers=h(admin))).status_code == 204


# ---------------------------------------------------------------- 9. 取り込みの報告の一覧


async def test_取り込みの報告の一覧(api, image_dir):  # noqa: F811
    from test_translation_review_import import A4_SPEC, import_fixture

    a = user()
    ids = await new_work(api, a)
    wid = ids["work"]
    assert (await op(api, wid, a, {"type": "set_work_settings", "page_spec": A4_SPEC})).status_code == 200
    first = (await import_fixture(api, wid, a, ids["episode"])).json()
    second = (await import_fixture(api, wid, a, ids["episode"])).json()
    r = await api.get(f"/works/{wid}/current-app-imports", headers=h(a))
    assert r.status_code == 200
    got = r.json()
    assert [x["id"] for x in got] == [second["id"], first["id"]] and "entries" not in got[0]
    assert got[0]["counts"] == second["counts"]
    assert (await api.get(f"/works/{wid}/current-app-imports?episode_id=none", headers=h(a))).json() == []
    assert (await api.get(f"/works/{wid}/current-app-imports", headers=h(user()))).status_code == 403
    assert TERMS


# ---------------------------------------------------------------- 10. 抜いた訳文の一覧と、足し直し


async def test_抜いた訳文の一覧と_同じ文字へ足し直す(api):
    a = user()
    ids = await new_work(api, a)
    wid = ids["work"]
    assert (await op(api, wid, a, {"type": "set_work_settings", "preferences": {"language": "ja"}})).status_code == 200
    tid, pid = "t1" + wid[2:], "p1" + wid[2:]
    assert (await op(api, wid, a, {"type": "add_panel", "id": pid, "page_id": ids["page1"], "order": 0})).status_code == 200
    r = await op(api, wid, a, {"type": "add_text_item", "id": tid, "panel_id": pid, "item_kind": "balloon",
                               "order": 0, "text": "こんにちは"})
    assert r.status_code == 200, r.text
    r = await op(api, wid, a, {"type": "set_text_translation", "text_item_id": tid, "language": "en", "text": "Hello"})
    assert r.status_code == 200, r.text
    tr = (await api.get(f"/works/{wid}/translations?language=en", headers=h(a))).json()["translations"][0]
    assert (await op(api, wid, a, {"type": "set_text_translation_removed", "id": tr["id"], "removed": True})).status_code == 200
    got = (await api.get(f"/works/{wid}/translations?language=en", headers=h(a))).json()
    assert got["translations"] == [] and got["missing_text_item_ids"] == [tid]
    assert [x["text"] for x in got["removed_translations"]] == ["Hello"] and got["removed_translations"][0]["id"] == tr["id"]
    # 抜いた訳文の文字へ足すと、同じ行を戻して書き直す
    r = await op(api, wid, a, {"type": "set_text_translation", "text_item_id": tid, "language": "en", "text": "Hi"})
    assert r.status_code == 200, r.text
    got = (await api.get(f"/works/{wid}/translations?language=en", headers=h(a))).json()
    assert [x["text"] for x in got["translations"]] == ["Hi"] and got["removed_translations"] == []
    assert got["translations"][0]["id"] == tr["id"]
    # 取り消すと、また抜いた状態に戻る
    assert (await api.post(f"/works/{wid}/events/{r.json()['event_id']}/undo", headers=h(a))).status_code == 200
    got = (await api.get(f"/works/{wid}/translations?language=en", headers=h(a))).json()
    assert got["translations"] == [] and len(got["removed_translations"]) == 1
    assert json.dumps(got, ensure_ascii=False)
