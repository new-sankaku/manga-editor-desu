"""人とAIのどちらが作っても同じ流れに乗るか。人の手の印をAIが上書きしないか。"""

import io
import json
import uuid

import pytest
from conftest import h, new_work, user
from PIL import Image

from v3server.database_engine import get_sessionmaker
from v3server.operations import operation_submit_and_undo
from v3server.request_actor import Actor
from v3server.v3_error_types import AiInvolvementRefused, HumanHandProtected, Invalid

PAGE_SPEC = {"frame_width_mm": 150, "frame_height_mm": 220, "trim_width_mm": 182, "trim_height_mm": 257,
             "bleed_mm": 3, "gutter_x_mm": 2, "gutter_y_mm": 5}


TERMS = {"commercial_use": "yes", "rights_holder": "作者本人", "training_use": "no", "credit_required": "no",
         "terms_note": "作者と書面で確認", "checked_on": "2026-10-08"}


def name_panel(n: int, text: str) -> dict:
    return {"n": n, "size": "中", "shape": "四角", "shot": "胸から上", "angle": "目の高さ",
            "people": [{"name": "A", "face": "中", "facing": "正面"}], "background": "簡略", "scene": 1, "role": "起",
            "hook": False, "content": text, "balloons": [{"speaker": "A", "kind": "台詞", "text": text}], "sfx": []}


def name_page(number: int, texts: list[str], first_n: int = 1) -> dict:
    panels = [name_panel(first_n + i, t) for i, t in enumerate(texts)]
    return {"page": number, "spread": False, "rows": [[p["n"] for p in panels]], "panels": panels}


async def op(api, wid, u, body):
    return await api.post(f"/works/{wid}/ops", headers=h(u), json=body)


async def ai_op(authz, wid, on_behalf_of, body):
    async with get_sessionmaker()() as session:
        return await operation_submit_and_undo.submit(
            session, authz, Actor(kind="ai", id="ai-test", on_behalf_of=on_behalf_of), wid, body)


async def allow_ai(api, wid, u, *tasks, mode="ai_auto"):
    """作業のAIの関与を選ぶ（既定は「AIが案を出し人が選ぶ」なので、AIに直接変えさせる試験で使う）。"""
    for t in tasks:
        r = await op(api, wid, u, {"type": "set_ai_involvement", "task": t, "mode": mode})
        assert r.status_code == 200, r.text


async def work_json(api, wid, u):
    return (await api.get(f"/works/{wid}", headers=h(u))).json()


async def test_人が変えた項目はAIが変えられず_ほかの項目は変えられる(api, authz):
    a = user()
    ids = await new_work(api, a)
    wid, pid = ids["work"], uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "add_panel", "id": pid, "page_id": ids["page1"], "order": 1})).status_code == 200
    frame = {"polygon_mm": [[0, 0], [150, 0], [150, 70], [0, 70]], "bleeds": False}
    assert (await op(api, wid, a, {"type": "update_panel", "id": pid, "frame": frame})).status_code == 200
    panel = next(p for p in (await work_json(api, wid, a))["panels"] if p["id"] == pid)
    # 人が足したコマなので読む順にも印が付く
    assert panel["human_hand_fields"] == ["frame", "order"]
    await allow_ai(api, wid, a, "name", "panel_layout")

    # 人が引いた枠をAIは変えられない。中身は変えられる
    with pytest.raises(HumanHandProtected):
        await ai_op(authz, wid, a, {"type": "update_panel", "id": pid, "frame": {"polygon_mm": [[0, 0], [1, 0], [1, 1]],
                                                                               "bleeds": False}})
    await ai_op(authz, wid, a, {"type": "update_panel", "id": pid, "content": {"content": "AIの中身"}})
    # AIは人の手の印を外せない。人は外せる
    with pytest.raises(HumanHandProtected):
        await ai_op(authz, wid, a, {"type": "update_panel", "id": pid, "human_hand_fields": []})
    assert (await op(api, wid, a, {"type": "update_panel", "id": pid, "human_hand_fields": []})).status_code == 200
    await ai_op(authz, wid, a, {"type": "update_panel", "id": pid, "frame": frame})
    # 確定印の付いたコマはAIが何も変えられず、抜くこともできない
    assert (await op(api, wid, a, {"type": "update_panel", "id": pid, "human_confirmed": True})).status_code == 200
    with pytest.raises(HumanHandProtected):
        await ai_op(authz, wid, a, {"type": "update_panel", "id": pid, "content": {"content": "x"}})
    with pytest.raises(HumanHandProtected):
        await ai_op(authz, wid, a, {"type": "set_removed", "target_kind": "panel", "id": pid, "removed": True})


async def test_AIの案と人の案と取り込みの案が同じ形で採用される(api, authz):
    a = user()
    ids = await new_work(api, a)
    wid, ep = ids["work"], ids["episode"]
    assert (await op(api, wid, a, {"type": "set_work_settings", "page_spec": PAGE_SPEC,
                                   "first_page_is_left": True})).status_code == 200
    # 作り手を偽れない
    r = await op(api, wid, a, {"type": "submit_name_proposal", "episode_id": ep, "made_by": "ai",
                               "pages": [name_page(1, ["x"])]})
    assert r.status_code == 422

    # AIの案を人が採用する：書いた項目に人の手の印は付かない
    ai_prop = uuid.uuid4().hex
    await ai_op(authz, wid, a, {"type": "submit_name_proposal", "id": ai_prop, "episode_id": ep, "made_by": "ai",
                                "pages": [name_page(1, ["AI1", "AI2"]), name_page(2, ["AI3"], 3)]})
    assert (await op(api, wid, a, {"type": "apply_name_proposal", "id": ai_prop})).status_code == 200
    w = await work_json(api, wid, a)
    p1 = [p for p in w["panels"] if p["page_id"] == ids["page1"] and not p["removed"]]
    assert sorted(p["content"]["content"] for p in p1) == ["AI1", "AI2"]
    assert all(p["human_hand_fields"] == [] for p in p1)
    draft = (await api.get(f"/works/{wid}/episodes/{ep}/name-draft", headers=h(a))).json()
    assert [len(pg["panels"]) for pg in draft["pages"]] == [2, 1]
    assert draft["reading_direction"] == "right_to_left"

    # 取り込みの案を人が採用する：人の手の印が付く
    imp = uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "submit_name_proposal", "id": imp, "episode_id": ep, "made_by": "imported",
                                   "pages": [name_page(1, ["取込1"])]})).status_code == 200
    r = await op(api, wid, a, {"type": "apply_name_proposal", "id": imp})
    assert r.status_code == 200, r.text
    w = await work_json(api, wid, a)
    p1 = sorted([p for p in w["panels"] if p["page_id"] == ids["page1"] and not p["removed"]], key=lambda p: p["order"])
    assert [p["content"]["content"] for p in p1] == ["取込1"]
    assert "content" in p1[0]["human_hand_fields"]
    page1 = next(p for p in w["pages"] if p["id"] == ids["page1"])
    assert page1["human_hand_fields"] == ["layout"]

    # 取り消すと、取り込む前（AIの案の状態）に戻る
    undo = await api.post(f"/works/{wid}/events/{r.json()['event_id']}/undo", headers=h(a))
    assert undo.status_code == 200, undo.text
    w = await work_json(api, wid, a)
    p1 = [p for p in w["panels"] if p["page_id"] == ids["page1"] and not p["removed"]]
    assert sorted(p["content"]["content"] for p in p1) == ["AI1", "AI2"]


async def test_AIが採用すると人の手の所は残し_残した所を記録する(api, authz):
    a = user()
    ids = await new_work(api, a)
    wid, ep = ids["work"], ids["episode"]
    human_prop = uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "submit_name_proposal", "id": human_prop, "episode_id": ep,
                                   "made_by": "human", "pages": [name_page(1, ["人1", "人2"])]})).status_code == 200
    assert (await op(api, wid, a, {"type": "apply_name_proposal", "id": human_prop})).status_code == 200

    ai_prop = uuid.uuid4().hex
    await ai_op(authz, wid, a, {"type": "submit_name_proposal", "id": ai_prop, "episode_id": ep, "made_by": "ai",
                                "pages": [name_page(1, ["AI1"])]})
    # 既定（AIが案を出し人が選ぶ）では、AIは採用できない
    with pytest.raises(AiInvolvementRefused):
        await ai_op(authz, wid, a, {"type": "apply_name_proposal", "id": ai_prop})
    await allow_ai(api, wid, a, "name", "panel_layout")
    event = await ai_op(authz, wid, a, {"type": "apply_name_proposal", "id": ai_prop})
    # 人の手の所に当たった変更は、捨てずに判断待ちに置く
    assert event.inverse["held_change_ids"]
    held = (await api.get(f"/works/{wid}/held-changes", headers=h(a))).json()
    assert {x["field"] for x in held} >= {"content", "removed"}
    w = await work_json(api, wid, a)
    p1 = sorted([p for p in w["panels"] if p["page_id"] == ids["page1"] and not p["removed"]], key=lambda p: p["order"])
    # 人が作った2コマは中身も数もそのまま
    assert [p["content"]["content"] for p in p1] == ["人1", "人2"]


def png_bytes(w: int = 64, h_: int = 32) -> bytes:
    buf = io.BytesIO()
    Image.new("L", (w, h_), 255).save(buf, format="PNG", dpi=(600, 600))
    return buf.getvalue()


async def test_人が描いた絵と持ち込んだ絵を登録してコマに使う(api, authz, tmp_path, monkeypatch):
    from v3server.server_settings import get_settings
    monkeypatch.setattr(get_settings(), "image_dir", str(tmp_path))
    a = user()
    ids = await new_work(api, a)
    wid, pid = ids["work"], uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "add_panel", "id": pid, "page_id": ids["page1"], "order": 1})).status_code == 200

    # 持ち込んだ絵は元を書かないと登録できない
    files = {"image": ("a.png", png_bytes(), "image/png")}
    r = await api.post(f"/works/{wid}/images", headers=h(a), files=files,
                       data={"role": "panel_art", "origin": "imported", "panel_id": pid})
    assert r.status_code == 422
    r = await api.post(f"/works/{wid}/images", headers=h(a), files=files,
                       data={"role": "panel_art", "origin": "imported", "panel_id": pid, "source_note": "作者の手描き"})
    assert r.status_code == 422  # 利用の条件が無い
    r = await api.post(f"/works/{wid}/images", headers=h(a), files=files,
                       data={"role": "panel_art", "origin": "imported", "panel_id": pid, "source_note": "作者の手描き",
                             "usage_terms": json.dumps(TERMS)})
    assert r.status_code == 201, r.text
    img = r.json()["id"]
    got = (await api.get(f"/works/{wid}/images", headers=h(a), params={"panel_id": pid})).json()
    assert [(g["origin"], g["width"], g["height"], g["dpi"]) for g in got] == [("imported", 64, 32, 600)]
    assert (await api.get(f"/works/{wid}/images/{img}/file", headers=h(a))).content == png_bytes()
    # 絵でないものは受け付けない
    r = await api.post(f"/works/{wid}/images", headers=h(a), files={"image": ("x.png", b"not image", "image/png")},
                       data={"role": "panel_art", "origin": "human_drawn"})
    assert r.status_code == 422

    # 人が選んだ絵は、AIが別の絵に替えられない
    assert (await op(api, wid, a, {"type": "update_panel", "id": pid, "image_id": img})).status_code == 200
    with pytest.raises(HumanHandProtected):
        await ai_op(authz, wid, a, {"type": "update_panel", "id": pid, "image_id": None})
    # AIが登録するのは生成した絵だけで、依頼が要る
    with pytest.raises(Invalid):
        await ai_op(authz, wid, a, {"type": "register_image", "role": "panel_art", "origin": "human_drawn",
                                    "panel_id": pid, "sha256": "0" * 64, "media_type": "image/png", "width": 1,
                                    "height": 1})
    with pytest.raises(Invalid):
        await ai_op(authz, wid, a, {"type": "register_image", "role": "panel_art", "origin": "generated",
                                    "panel_id": pid, "sha256": "0" * 64, "media_type": "image/png", "width": 1,
                                    "height": 1})


async def test_今のネームも案も同じ検査にかかり_使った閾値が残る(api, authz):
    a = user()
    ids = await new_work(api, a)
    wid, ep = ids["work"], ids["episode"]
    assert (await op(api, wid, a, {"type": "set_work_settings", "page_spec": PAGE_SPEC,
                                   "first_page_is_left": True})).status_code == 200
    assert (await op(api, wid, a, {"type": "set_threshold", "key": "panels_per_page_max", "value": {"value": 1},
                                   "source": "試験", "status": "unverified"})).status_code == 200
    prop = uuid.uuid4().hex
    await ai_op(authz, wid, a, {"type": "submit_name_proposal", "id": prop, "episode_id": ep, "made_by": "ai",
                                "pages": [name_page(1, ["1", "2"]), name_page(2, ["3"], 3)]})

    def panel_count(run):
        return next(r for r in run["report"]["results"] if r["threshold_key"] == "panels_per_page_max")

    # 採用する前の案を検査する。1ページ目が2コマなので上限1を超える
    r = await api.post(f"/works/{wid}/episodes/{ep}/name-checks", headers=h(a), json={"proposal_id": prop})
    assert r.status_code == 201, r.text
    run = r.json()
    assert panel_count(run)["status"] == "不合格"
    assert run["thresholds_used"]["panels_per_page_max"]["status"] == "unverified"

    # 採用した後の今のページとコマを検査しても、同じ結果になる
    assert (await op(api, wid, a, {"type": "apply_name_proposal", "id": prop})).status_code == 200
    r = await api.post(f"/works/{wid}/episodes/{ep}/name-checks", headers=h(a), json={})
    assert r.status_code == 201, r.text
    assert panel_count(r.json())["status"] == "不合格"

    # 閾値を rejected にすると使わず、値だけ返す
    assert (await op(api, wid, a, {"type": "set_threshold", "key": "panels_per_page_max", "value": {"value": 1},
                                   "source": "試験", "status": "rejected"})).status_code == 200
    r = await api.post(f"/works/{wid}/episodes/{ep}/name-checks", headers=h(a), json={})
    assert panel_count(r.json())["status"] == "閾値未設定"
    assert len((await api.get(f"/works/{wid}/episodes/{ep}/name-checks", headers=h(a))).json()) == 3
