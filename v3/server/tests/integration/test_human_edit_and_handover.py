"""人が直接直す（文字・絵・層・人の手の範囲）と、人とAIの受け渡し（判断待ち・AIの関与・コマ割りの計算・取り込み・絵の版）。
PostgreSQL・OpenFGA を実際に使う。"""

import io
import json
import uuid

import pytest
from conftest import h, new_work, user
from PIL import Image
from sqlalchemy import select
from test_comfyui_pipeline import (  # noqa: F401  (fake_comfy は fixture)
    SlowFakeComfy,
    fake_comfy,
)
from test_human_ai_interchange import (
    PAGE_SPEC,
    TERMS,
    ai_op,
    allow_ai,
    name_page,
    op,
    work_json,
)
from test_queue import admin, until_status  # noqa: F401  (admin は fixture)

from v3server import image_intake
from v3server.canonical_tables.image_file_tables import ImageIntakeScreening
from v3server.database_engine import get_sessionmaker
from v3server.server_settings import get_settings
from v3server.v3_error_types import (
    AiInvolvementRefused,
    Forbidden,
    Invalid,
)


def png_bytes(w: int = 64, h_: int = 32, shade: int = 255) -> bytes:
    buf = io.BytesIO()
    Image.new("L", (w, h_), shade).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def image_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "image_dir", str(tmp_path))
    return tmp_path


async def one_page_work(api, a):
    """1ページだけの話（2ページ目は抜く。中身の無いページは見開きかどうかも未定で、ネームの形にできないため）。"""
    ids = await new_work(api, a)
    r = await op(api, ids["work"], a, {"type": "set_removed", "target_kind": "page", "id": ids["page2"], "removed": True})
    assert r.status_code == 200, r.text
    return ids


async def setup_name(api, a, texts=("1", "2")):
    """作品の寸法を決め、人のネームの案を採用して、1ページ目に文字のあるコマを作る。"""
    ids = await one_page_work(api, a)
    wid, ep = ids["work"], ids["episode"]
    assert (await op(api, wid, a, {"type": "set_work_settings", "page_spec": PAGE_SPEC,
                                   "first_page_is_left": True})).status_code == 200
    page = name_page(1, list(texts))
    page["row_height_ratios"] = [1.0]
    page["cell_width_ratios"] = [[1.0] * len(texts)]
    prop = uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "submit_name_proposal", "id": prop, "episode_id": ep, "made_by": "human",
                                   "pages": [page]})).status_code == 200
    assert (await op(api, wid, a, {"type": "apply_name_proposal", "id": prop})).status_code == 200
    return ids


def live(rows, **kw):
    return [r for r in rows if not r["removed"] and all(r[k] == v for k, v in kw.items())]


async def upload(api, wid, a, origin="human_drawn", data=None, **form):
    files = {"image": ("a.png", data or png_bytes(), "image/png")}
    body = {"role": "panel_art", "origin": origin} | form
    return await api.post(f"/works/{wid}/images", headers=h(a), files=files, data=body)


# ---------------------------------------------------------------- 文字


async def test_人が文字を足し_直し_抜き_取り消せる_検査も同じにかかる(api, authz):
    a = user()
    ids = await setup_name(api, a)
    wid, ep = ids["work"], ids["episode"]
    w = await work_json(api, wid, a)
    panel1 = min(live(w["panels"], page_id=ids["page1"]), key=lambda p: p["order"])
    (balloon,) = live(w["text_items"], panel_id=panel1["id"])
    assert balloon["item_kind"] == "balloon" and balloon["text"] == "1"

    # 人が直すと、直した項目に人の手の印が付く
    r = await op(api, wid, a, {"type": "update_text_item", "id": balloon["id"], "text": "直した", "balloon_kind": "心の声",
                               "writing_direction": "vertical", "font_size_pt": 9, "box_mm": [10, 10, 40, 60],
                               "tail_target_mm": [30, 80], "order": 0})
    assert r.status_code == 200, r.text
    update_event = r.json()["event_id"]
    item = next(t for t in (await work_json(api, wid, a))["text_items"] if t["id"] == balloon["id"])
    assert item["text"] == "直した" and item["box_mm"] == [10, 10, 40, 60]
    assert set(item["human_hand_fields"]) >= {"text", "balloon_kind", "writing_direction", "font_size_pt", "box_mm",
                                               "tail_target_mm"}
    # 描き文字とナレーションの箱を足す。値の確かめは人もAIも同じ
    caption, sfx = uuid.uuid4().hex, uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "add_text_item", "id": caption, "panel_id": panel1["id"],
                                   "item_kind": "caption", "order": 1, "text": "その頃",
                                   "balloon_kind": "ナレーション", "writing_direction": "horizontal"})).status_code == 200
    assert (await op(api, wid, a, {"type": "add_text_item", "id": sfx, "panel_id": panel1["id"], "item_kind": "drawn_sfx",
                                   "order": 0, "text": "ドン"})).status_code == 200
    bad = {"type": "add_text_item", "panel_id": panel1["id"], "item_kind": "drawn_sfx", "order": 1, "text": "x",
           "speaker": "A"}
    assert (await op(api, wid, a, bad)).status_code == 422
    await allow_ai(api, wid, a, "name")
    with pytest.raises(Invalid):
        await ai_op(authz, wid, a, bad)

    # 人が直した文字も、ネームの形と検査に同じように出る
    draft = (await api.get(f"/works/{wid}/episodes/{ep}/name-draft", headers=h(a))).json()
    p1 = draft["pages"][0]["panels"][0]
    assert [b["text"] for b in p1["balloons"]] == ["直した", "その頃"] and p1["sfx"] == ["ドン"]
    run = (await api.post(f"/works/{wid}/episodes/{ep}/name-checks", headers=h(a), json={})).json()
    chars = next(x for x in run["report"]["results"] if x["check_id"] == "balloon_chars")
    assert chars["status"] == "閾値未設定" and chars["value"] is not None

    # AIは人が直した項目を書かず、判断待ちに置く
    ev = await ai_op(authz, wid, a, {"type": "update_text_item", "id": balloon["id"], "text": "AI"})
    assert [x["field"] for x in ev.held_changes] == ["text"]
    # 抜いて戻す。直したのを取り消すと元に戻る
    assert (await op(api, wid, a, {"type": "set_removed", "target_kind": "text_item", "id": sfx,
                                   "removed": True})).status_code == 200
    r = await api.post(f"/works/{wid}/events/{update_event}/undo", headers=h(a))
    assert r.status_code == 200, r.text
    item = next(t for t in (await work_json(api, wid, a))["text_items"] if t["id"] == balloon["id"])
    assert item["text"] == "1" and "box_mm" not in item["human_hand_fields"]


async def open_held(api, wid, a) -> list[dict]:
    return (await api.get(f"/works/{wid}/held-changes", headers=h(a))).json()


async def test_前からある操作でも_AIの変更が人の手の所に当たるとその項目だけ判断待ちにし_残りは当てる(api, authz):
    a = user()
    ids = await setup_name(api, a)
    wid = ids["work"]
    w = await work_json(api, wid, a)
    panel1 = min(live(w["panels"], page_id=ids["page1"]), key=lambda p: p["order"])
    (balloon,) = live(w["text_items"], panel_id=panel1["id"])
    # セリフにだけ人の手の印を残す
    assert (await op(api, wid, a, {"type": "update_text_item", "id": balloon["id"],
                                   "human_hand_fields": ["text"]})).status_code == 200
    await allow_ai(api, wid, a, "name", "finishing")

    # AIがセリフ（印あり）と不透明度（印なし）を1回で変える。不透明度は当て、セリフは判断待ち
    ev = await ai_op(authz, wid, a, {"type": "update_text_item", "id": balloon["id"], "text": "AIのセリフ",
                                     "opacity": 0.5})
    assert [(x["target_table"], x["target_id"], x["field"]) for x in ev.held_changes] == [
        ("text_items", balloon["id"], "text")]
    # 出来事の一覧にも残る
    (listed,) = (await api.get(f"/works/{wid}/events", headers=h(a), params={"after": ev.seq - 1})).json()
    assert listed["id"] == ev.id and listed["held_changes"] == ev.held_changes

    async def item():
        return next(t for t in (await work_json(api, wid, a))["text_items"] if t["id"] == balloon["id"])

    now = await item()
    assert (now["text"], now["opacity"], now["human_hand_fields"]) == (balloon["text"], 0.5, ["text"])
    (held,) = await open_held(api, wid, a)
    assert (held["id"], held["field"], held["proposed_value"], held["current_value"]) == (
        ev.held_changes[0]["id"], "text", "AIのセリフ", balloon["text"])

    # 取り消すと、当てた項目が戻り、判断待ちは下がる。やり直すと、当てた項目も判断待ちも戻る
    r = await api.post(f"/works/{wid}/events/{ev.id}/undo", headers=h(a))
    assert r.status_code == 200, r.text
    assert (await item())["opacity"] == balloon["opacity"] and await open_held(api, wid, a) == []
    r = await api.post(f"/works/{wid}/events/{r.json()['event_id']}/undo", headers=h(a))
    assert r.status_code == 200, r.text
    assert (await item())["opacity"] == 0.5 and [x["id"] for x in await open_held(api, wid, a)] == [held["id"]]

    # 人が採ると、その値が人の判断として入る
    r = await op(api, wid, a, {"type": "resolve_held_change", "id": held["id"], "decision": "accept"})
    assert r.status_code == 200, r.text
    now = await item()
    assert now["text"] == "AIのセリフ" and "text" in now["human_hand_fields"]


async def test_AIの案が人の直した所に当たると判断待ちになり_人が採る_採らない_戻すを選べる(api, authz):
    a = user()
    ids = await setup_name(api, a)
    wid, ep = ids["work"], ids["episode"]
    w = await work_json(api, wid, a)
    panel1 = min(live(w["panels"], page_id=ids["page1"]), key=lambda p: p["order"])
    (balloon,) = live(w["text_items"], panel_id=panel1["id"])
    # 人の案で入った値の印を全部外し、セリフだけ人が直したことにする
    await op(api, wid, a, {"type": "update_panel", "id": panel1["id"], "human_hand_fields": []})
    for p in live(w["panels"], page_id=ids["page1"]):
        await op(api, wid, a, {"type": "update_panel", "id": p["id"], "human_hand_fields": []})
    await op(api, wid, a, {"type": "update_page", "id": ids["page1"], "human_hand_fields": []})
    for t in live(w["text_items"]):
        await op(api, wid, a, {"type": "update_text_item", "id": t["id"], "human_hand_fields": []})
    assert (await op(api, wid, a, {"type": "update_text_item", "id": balloon["id"], "text": "人のセリフ"})).status_code == 200

    # AIの案（セリフをAIのものに変える）。人が採用しても、人の直した所は書かずに判断待ちへ
    page = name_page(1, ["AIのセリフ", "AI2"])
    page |= {"row_height_ratios": [1.0], "cell_width_ratios": [[1.0, 1.0]]}
    prop = uuid.uuid4().hex
    await ai_op(authz, wid, a, {"type": "submit_name_proposal", "id": prop, "episode_id": ep, "made_by": "ai",
                                "pages": [page]})
    r = await op(api, wid, a, {"type": "apply_name_proposal", "id": prop})
    assert r.status_code == 200, r.text
    # 判断待ちに置いた項目は、操作の返事で呼んだ側に返る
    assert [(x["target_id"], x["field"]) for x in r.json()["held_changes"]] == [(balloon["id"], "text")]
    texts = {t["id"]: t["text"] for t in (await work_json(api, wid, a))["text_items"]}
    assert texts[balloon["id"]] == "人のセリフ" and "AI2" in texts.values()
    (held,) = (await api.get(f"/works/{wid}/held-changes", headers=h(a))).json()
    assert (held["target_table"], held["field"], held["proposed_value"], held["current_value"]) == (
        "text_items", "text", "AIのセリフ", "人のセリフ")

    # AIは判断待ちを決められない
    with pytest.raises(Forbidden):
        await ai_op(authz, wid, a, {"type": "resolve_held_change", "id": held["id"], "decision": "accept"})
    # 人が採ると、その値が人の判断として入る。取り消すと判断待ちと元の値に戻る
    r = await op(api, wid, a, {"type": "resolve_held_change", "id": held["id"], "decision": "accept"})
    assert r.status_code == 200, r.text
    texts = {t["id"]: t for t in (await work_json(api, wid, a))["text_items"]}
    assert texts[balloon["id"]]["text"] == "AIのセリフ" and "text" in texts[balloon["id"]]["human_hand_fields"]
    assert (await api.post(f"/works/{wid}/events/{r.json()['event_id']}/undo", headers=h(a))).status_code == 200
    texts = {t["id"]: t for t in (await work_json(api, wid, a))["text_items"]}
    assert texts[balloon["id"]]["text"] == "人のセリフ"
    assert [x["status"] for x in (await api.get(f"/works/{wid}/held-changes", headers=h(a))).json()] == ["open"]
    # 採らない
    assert (await op(api, wid, a, {"type": "resolve_held_change", "id": held["id"],
                                   "decision": "reject"})).status_code == 200
    assert (await api.get(f"/works/{wid}/held-changes", headers=h(a))).json() == []
    # 案の採用を取り消すと、判断待ちも withdrawn（決めた後なら残る）
    assert (await api.post(f"/works/{wid}/events/{r.json()['event_id']}/undo", headers=h(a))).status_code == 409


# ---------------------------------------------------------------- AIの関与で工程の進み方が変わる


async def test_AIの関与の4択に従って_案_採用_作業が止まる(api, authz):
    a = user()
    ids = await setup_name(api, a)
    wid, ep = ids["work"], ids["episode"]
    got = {x["task"]: x for x in (await api.get(f"/works/{wid}/ai-involvement", headers=h(a))).json()}
    assert got["name"] == {"task": "name", "title": got["name"]["title"], "mode": "ai_proposes", "chosen": False}
    page = name_page(1, ["x"])

    # AIを使わない・人が作りAIは検査だけ：AIは案も出せない
    for mode in ("no_ai", "human_makes_ai_checks"):
        await allow_ai(api, wid, a, "name", mode=mode)
        with pytest.raises(AiInvolvementRefused):
            await ai_op(authz, wid, a, {"type": "submit_name_proposal", "episode_id": ep, "made_by": "ai",
                                        "pages": [page]})
    # 人は関与に依らず作れる
    assert (await op(api, wid, a, {"type": "submit_name_proposal", "episode_id": ep, "made_by": "human",
                                   "pages": [page]})).status_code == 200
    # AIが案を出し人が選ぶ：案は出せるが、採用とコマの値の変更はできない
    await allow_ai(api, wid, a, "name", mode="ai_proposes")
    prop = uuid.uuid4().hex
    await ai_op(authz, wid, a, {"type": "submit_name_proposal", "id": prop, "episode_id": ep, "made_by": "ai",
                                "pages": [page]})
    with pytest.raises(AiInvolvementRefused):
        await ai_op(authz, wid, a, {"type": "apply_name_proposal", "id": prop})
    panel = live((await work_json(api, wid, a))["panels"], page_id=ids["page1"])[0]
    await op(api, wid, a, {"type": "update_panel", "id": panel["id"], "human_hand_fields": []})
    with pytest.raises(AiInvolvementRefused):
        await ai_op(authz, wid, a, {"type": "update_panel", "id": panel["id"], "content": {"content": "AI"}})
    # AIに任せる：変えられる。作品の設定のようなAIの出せない操作は関与に依らず止まる
    await allow_ai(api, wid, a, "name")
    await ai_op(authz, wid, a, {"type": "update_panel", "id": panel["id"], "content": {"content": "AI"}})
    with pytest.raises(Forbidden):
        await ai_op(authz, wid, a, {"type": "set_ai_involvement", "task": "name", "mode": "ai_auto"})
    # 既定に戻す
    assert (await op(api, wid, a, {"type": "set_ai_involvement", "task": "name", "mode": None})).status_code == 200
    got = {x["task"]: x for x in (await api.get(f"/works/{wid}/ai-involvement", headers=h(a))).json()}
    assert got["name"]["chosen"] is False


# ---------------------------------------------------------------- コマ割り：人が描く・AIが割る・人が一部を固定する


async def test_人が描いた斜めの枠を固定して残りをコマ割りの計算が割り_人の枠は上書きしない(api, authz):
    a = user()
    ids = await setup_name(api, a, texts=("1", "2", "3"))
    wid, ep = ids["work"], ids["episode"]
    assert (await op(api, wid, a, {"type": "set_threshold", "key": "panel_short_side_min_mm", "value": {"value": 10},
                                   "source": "試験", "status": "unverified"})).status_code == 200
    rows = sorted(live((await work_json(api, wid, a))["panels"], page_id=ids["page1"]), key=lambda p: p["order"])
    # 人の案の印を外し（AIが割れるように）、コマ1だけ人が斜めの枠を描く
    for p in rows:
        await op(api, wid, a, {"type": "update_panel", "id": p["id"], "human_hand_fields": []})
    await op(api, wid, a, {"type": "update_page", "id": ids["page1"], "human_hand_fields": []})
    slanted = {"polygon_mm": [[100, 0], [150, 0], [150, 220], [96, 220]], "bleeds": False}
    assert (await op(api, wid, a, {"type": "update_panel", "id": rows[0]["id"], "frame": slanted})).status_code == 200
    # 形の崩れた枠は、人でも受け付けない
    r = await op(api, wid, a, {"type": "update_panel", "id": rows[1]["id"], "frame": {"polygon_mm": [[0, 0]]}})
    assert r.status_code == 422

    # 既定（AIが案を出し人が選ぶ）：案のまま止まる
    r = await api.post(f"/works/{wid}/episodes/{ep}/panel-layout-proposals", headers=h(a))
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["applied"] is False and out["pinned_panels"] == [1]
    props = (await api.get(f"/works/{wid}/episodes/{ep}/name-proposals", headers=h(a))).json()
    prop = next(p for p in props if p["id"] == out["proposal_id"])
    assert prop["task"] == "panel_layout" and prop["made_by"] == "ai"

    # コマ割りをAIに任せる：計算の結果がそのまま入る。人の枠は動かず印も残る
    await allow_ai(api, wid, a, "panel_layout")
    out = (await api.post(f"/works/{wid}/episodes/{ep}/panel-layout-proposals", headers=h(a))).json()
    assert out["applied"] is True and out["held_change_ids"] == []
    rows = sorted(live((await work_json(api, wid, a))["panels"], page_id=ids["page1"]), key=lambda p: p["order"])
    assert rows[0]["frame"] == slanted and rows[0]["human_hand_fields"] == ["frame"]
    assert all(p["frame"] and p["human_hand_fields"] == [] for p in rows[1:])
    # AIの割りを人が直すと、次の計算はその枠も固定する
    fixed = {"polygon_mm": [[0, 0], [45, 0], [45, 220], [0, 220]], "bleeds": False}
    assert (await op(api, wid, a, {"type": "update_panel", "id": rows[2]["id"], "frame": fixed})).status_code == 200
    out = (await api.post(f"/works/{wid}/episodes/{ep}/panel-layout-proposals", headers=h(a))).json()
    assert out["pinned_panels"] == [1, 3]
    rows = sorted(live((await work_json(api, wid, a))["panels"], page_id=ids["page1"]), key=lambda p: p["order"])
    assert rows[2]["frame"] == fixed
    # 人の描いた枠にも、計算の枠にも、同じ検査がかかる
    run = await api.post(f"/works/{wid}/episodes/{ep}/name-checks", headers=h(a), json={})
    assert run.status_code == 201, run.text
    # コマ割りをAIに使わせない作品では、計算も頼めない
    await allow_ai(api, wid, a, "panel_layout", mode="no_ai")
    assert (await api.post(f"/works/{wid}/episodes/{ep}/panel-layout-proposals", headers=h(a))).status_code == 409


async def test_最小の大きさの閾値が無ければ割りを計算しない(api):
    a = user()
    ids = await setup_name(api, a)
    r = await api.post(f"/works/{ids['work']}/episodes/{ids['episode']}/panel-layout-proposals", headers=h(a))
    assert r.status_code == 422 and "panel_short_side_min_mm" in r.json()["detail"]


async def test_人が描いたネームを取り込み_分からない所は未定のまま同じ検査にかかる(api):
    a = user()
    ids = await one_page_work(api, a)
    wid, ep = ids["work"], ids["episode"]
    assert (await op(api, wid, a, {"type": "set_work_settings", "page_spec": PAGE_SPEC,
                                   "first_page_is_left": True})).status_code == 200
    doc = {"format": "manga-editor-import", "version": 1, "pages": [{
        "index": 0, "source_file": "001.jpg", "width": 1820, "height": 2570,
        "panels": [{"id": "p1", "reading_order": 1, "shape": "normal", "is_bleed": False,
                    "points": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.5], [0.1, 0.5]]},
                   {"id": "p2", "reading_order": 2, "shape": "normal", "is_bleed": False,
                    "points": [[0.1, 0.52], [0.9, 0.52], [0.9, 0.9], [0.1, 0.9]]}],
        "balloons": [{"id": "b1", "panel_id": "p1", "reading_order": 1, "type": "normal",
                      "bbox": {"x": 0.6, "y": 0.15, "w": 0.1, "h": 0.15}, "text": "取り込んだセリフ", "excluded": False},
                     {"id": "b2", "panel_id": "p2", "reading_order": 2, "type": "normal",
                      "bbox": {"x": 0.6, "y": 0.6, "w": 0.1, "h": 0.1}, "text": "?", "excluded": True,
                      "exclusion_reason": "低い"}]}]}
    r = await api.post(f"/works/{wid}/episodes/{ep}/name-imports", headers=h(a), json={
        "document": doc, "image_covers": "trim", "first_page_number": 1, "first_panel_number": 1})
    assert r.status_code == 201, r.text
    assert [d["balloon_id"] for d in r.json()["dropped"]] == ["b2"]
    prop = r.json()["proposal_id"]
    props = (await api.get(f"/works/{wid}/episodes/{ep}/name-proposals", headers=h(a))).json()
    assert next(p for p in props if p["id"] == prop)["made_by"] == "imported"
    # 採用する前の案にも、採用した後にも、同じ検査がかかる。分からない項目の検査はデータなし
    for body in ({"proposal_id": prop}, None):
        if body is None:
            assert (await op(api, wid, a, {"type": "apply_name_proposal", "id": prop})).status_code == 200
            body = {}
        run = await api.post(f"/works/{wid}/episodes/{ep}/name-checks", headers=h(a), json=body)
        assert run.status_code == 201, run.text
        results = {x["check_id"]: x for x in run.json()["report"]["results"]}
        assert results["frame_bounds"]["status"] == "合格"
        assert results["same_shot_angle_next"]["status"] == "データなし"
        assert results["balloon_chars"]["status"] == "閾値未設定"
    w = await work_json(api, wid, a)
    texts = live(w["text_items"])
    assert [t["text"] for t in texts] == ["取り込んだセリフ"] and "text" in texts[0]["human_hand_fields"]
    draft = (await api.get(f"/works/{wid}/episodes/{ep}/name-draft", headers=h(a))).json()
    p2 = draft["pages"][0]["panels"][1]
    assert p2["balloons"] == [] and p2["size"] is None and p2["sfx"] is None
    # 形の崩れた文書は受け付けない
    bad = await api.post(f"/works/{wid}/episodes/{ep}/name-imports", headers=h(a), json={
        "document": {"format": "x"}, "image_covers": "trim", "first_page_number": 1, "first_panel_number": 1})
    assert bad.status_code == 422


# ---------------------------------------------------------------- 絵：差し替え・版・条件・置き場・層・入口


async def test_コマの絵を差し替えても前の版が残り_誰がどこからどの条件で作ったかをたどれる(api, authz, image_dir):
    a = user()
    ids = await new_work(api, a)
    wid, ep = ids["work"], ids["episode"]
    pid = uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "add_panel", "id": pid, "page_id": ids["page1"], "order": 1})).status_code == 200
    r = await api.post(f"/works/{wid}/panels/{pid}/image", headers=h(a),
                       files={"image": ("a.png", png_bytes(), "image/png")},
                       data={"origin": "imported", "source_note": "作者の下描き", "usage_terms": json.dumps(TERMS)})
    assert r.status_code == 201, r.text
    first = r.json()["id"]
    # 人が外のソフトで手を入れて戻す
    r = await api.post(f"/works/{wid}/panels/{pid}/image", headers=h(a),
                       files={"image": ("b.png", png_bytes(shade=200), "image/png")}, data={"origin": "human_edited"})
    assert r.status_code == 201, r.text
    second, select_event = r.json()["id"], r.json()["select_event_id"]
    assert r.json()["previous_image_id"] == first
    chain = (await api.get(f"/works/{wid}/images/{second}/lineage", headers=h(a))).json()
    assert [(v["image_id"], v["origin"], v["registered_by_id"]) for v in chain] == [
        (second, "human_edited", a), (first, "imported", a)]
    assert chain[1]["usage_terms"]["commercial_use"] == "yes" and not chain[1]["terms_missing"]
    prov = (await api.get(f"/works/{wid}/episodes/{ep}/image-provenance", headers=h(a))).json()
    assert [(x["panel_id"], x["used_as"], x["versions"][0]["image_id"]) for x in prov] == [(pid, "panel_image", second)]
    # 手を入れた絵に元の版が無ければ受け付けない
    assert (await upload(api, wid, a, origin="human_edited")).status_code == 422
    # 選んだのを取り消すと、前の絵に戻る（絵は消えない）
    assert (await api.post(f"/works/{wid}/events/{select_event}/undo", headers=h(a))).status_code == 200
    panel = next(p for p in (await work_json(api, wid, a))["panels"] if p["id"] == pid)
    assert panel["image_id"] == first
    assert {i["id"] for i in (await api.get(f"/works/{wid}/images", headers=h(a))).json()} == {first, second}


async def test_絵の切り抜きと置き場と層を人が直し_AIは人の所を変えられない(api, authz, image_dir):
    a = user()
    ids = await new_work(api, a)
    wid = ids["work"]
    pid = uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "add_panel", "id": pid, "page_id": ids["page1"], "order": 1})).status_code == 200
    img = (await upload(api, wid, a, panel_id=pid)).json()["id"]
    tone = (await upload(api, wid, a, data=png_bytes(shade=100), role="tone", panel_id=pid)).json()["id"]
    assert (await op(api, wid, a, {"type": "update_panel", "id": pid, "image_id": img})).status_code == 200
    # 絵の外の切り抜きは受け付けない
    big = {"crop_px": [0, 0, 65, 32], "dest_box_mm": [0, 0, 150, 70]}
    assert (await op(api, wid, a, {"type": "update_panel", "id": pid, "image_placement": big})).status_code == 422
    place = {"crop_px": [4, 2, 60, 30], "dest_box_mm": [0, 0, 150, 70], "rotation_deg": 0}
    r = await op(api, wid, a, {"type": "update_panel", "id": pid, "image_placement": place})
    assert r.status_code == 200, r.text
    panel = next(p for p in (await work_json(api, wid, a))["panels"] if p["id"] == pid)
    assert panel["image_placement"]["crop_px"] == [4, 2, 60, 30] and "image_placement" in panel["human_hand_fields"]
    await allow_ai(api, wid, a, "drawing")
    ev = await ai_op(authz, wid, a, {"type": "update_panel", "id": pid, "image_placement": None})
    assert [x["field"] for x in ev.held_changes] == ["image_placement"]

    # 層：線画とトーンを重ね、順・見せるか・不透明度を変え、取り消す
    line, tone_layer = uuid.uuid4().hex, uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "add_panel_layer", "id": line, "panel_id": pid, "role": "line_art",
                                   "image_id": img, "stack_order": 2})).status_code == 200
    assert (await op(api, wid, a, {"type": "add_panel_layer", "id": tone_layer, "panel_id": pid, "role": "tone",
                                   "image_id": tone, "stack_order": 1, "opacity": 0.5})).status_code == 200
    r = await op(api, wid, a, {"type": "update_panel_layer", "id": tone_layer, "stack_order": 3, "visible": False,
                               "opacity": 0.8})
    assert r.status_code == 200, r.text
    layer = next(x for x in (await work_json(api, wid, a))["panel_layers"] if x["id"] == tone_layer)
    assert (layer["stack_order"], layer["visible"], layer["opacity"]) == (3, False, 0.8)
    assert (await api.post(f"/works/{wid}/events/{r.json()['event_id']}/undo", headers=h(a))).status_code == 200
    layer = next(x for x in (await work_json(api, wid, a))["panel_layers"] if x["id"] == tone_layer)
    assert (layer["stack_order"], layer["visible"], layer["opacity"]) == (1, True, 0.5)
    ev = await ai_op(authz, wid, a, {"type": "update_panel_layer", "id": tone_layer, "opacity": 0.1})
    assert [x["field"] for x in ev.held_changes] == ["opacity"]
    ev = await ai_op(authz, wid, a, {"type": "set_removed", "target_kind": "panel_layer", "id": line, "removed": True})
    assert [x["field"] for x in ev.held_changes] == ["removed"]
    assert (await op(api, wid, a, {"type": "update_panel_layer", "id": tone_layer, "opacity": 2})).status_code == 422
    prov = (await api.get(f"/works/{wid}/episodes/{ids['episode']}/image-provenance", headers=h(a))).json()
    assert [x["used_as"] for x in prov] == ["panel_image", "layer", "layer"]


async def test_入口を通らない絵と_入口で止めた絵は登録しない(api, authz, image_dir, monkeypatch):
    a = user()
    ids = await new_work(api, a)
    wid = ids["work"]
    r = await upload(api, wid, a, page_id=ids["page1"])
    assert r.status_code == 201
    async with get_sessionmaker()() as session:
        rows = (await session.execute(select(ImageIntakeScreening).where(
            ImageIntakeScreening.work_id == wid))).scalars().all()
    assert [(x.entry, x.status, x.judge) for x in rows] == [("human_upload", "not_judged", None)]
    # 置き場を通っていない sha256 を操作で直接登録しようとしても断る
    r = await op(api, wid, a, {"type": "register_image", "role": "panel_art", "origin": "human_drawn", "sha256": "1" * 64,
                               "media_type": "image/png", "width": 1, "height": 1})
    assert r.status_code == 422 and "入口" in r.json()["detail"]

    async def block(data, work_id, entry):
        return image_intake.JudgeVerdict(blocked=True, detail="試験の判定")
    monkeypatch.setattr(image_intake, "INTAKE_JUDGES", [("試験", block)])
    r = await upload(api, wid, a, data=png_bytes(shade=10))
    assert r.status_code == 422 and "止めた" in r.json()["detail"]
    async with get_sessionmaker()() as session:
        statuses = (await session.execute(select(ImageIntakeScreening.status).where(
            ImageIntakeScreening.work_id == wid))).scalars().all()
    assert sorted(statuses) == ["blocked", "not_judged"]


async def test_人の手の範囲は人だけが決められる(api, authz, image_dir):
    a = user()
    ids = await new_work(api, a)
    wid = ids["work"]
    img = (await upload(api, wid, a, page_id=ids["page1"])).json()["id"]
    region = uuid.uuid4().hex
    r = await op(api, wid, a, {"type": "add_protected_region", "id": region, "image_id": img,
                               "polygon_px": [[0, 0], [10, 0], [10, 10]], "note": "顔は人が描いた"})
    assert r.status_code == 200, r.text
    assert (await op(api, wid, a, {"type": "add_protected_region", "image_id": img,
                                   "polygon_px": [[0, 0], [100, 0], [10, 10]]})).status_code == 422
    with pytest.raises(Forbidden):
        await ai_op(authz, wid, a, {"type": "set_protected_region_removed", "id": region, "removed": True})
    got = (await api.get(f"/works/{wid}/images/{img}/protected-regions", headers=h(a))).json()
    assert [(g["id"], g["removed"]) for g in got] == [(region, False)]
    assert (await api.post(f"/works/{wid}/events/{r.json()['event_id']}/undo", headers=h(a))).status_code == 200
    got = (await api.get(f"/works/{wid}/images/{img}/protected-regions", headers=h(a))).json()
    assert got[0]["removed"] is True


# ---------------------------------------------------------------- 持ち込んだ絵・人が手を入れた絵をAIの直しの元にする


class UploadingFakeComfy(SlowFakeComfy):
    """/upload/image を受け、上げた名前と /prompt に来た手順を残す。"""

    def __init__(self):
        super().__init__(finish_after=1)
        self.uploads, self.prompt = [], None

    def __call__(self, req):
        import httpx
        if req.url.path == "/upload/image":
            name = f"up{len(self.uploads)}.png"
            self.uploads.append(name)
            return httpx.Response(200, json={"name": name, "subfolder": "", "type": "input"})
        if req.url.path == "/prompt":
            self.prompt = json.loads(req.content)["prompt"]
        return super().__call__(req)


async def make_redraw_service(api, admin_user, action="propose"):
    name, process = f"comfy-{uuid.uuid4().hex[:6]}", f"redraw-{uuid.uuid4().hex[:6]}"
    sid = (await api.post("/services", headers=h(admin_user), json={
        "name": name, "kind": "image", "location": "local", "adapter": "comfyui", "endpoint": "http://comfy",
        "send_mode": "serial"})).json()["id"]
    workflow = {"3": {"class_type": "LoadImage", "inputs": {"image": "x"}},
                "4": {"class_type": "LoadImage", "inputs": {"image": "x"}},
                "9": {"class_type": "SaveImage", "inputs": {}}}
    r = await api.put(f"/services/{sid}/processes/{process}", headers=h(admin_user), json={
        "comfy_workflow": workflow, "comfy_wait_seconds": 30})
    assert r.status_code == 200, r.text
    r = await api.put(f"/routes/{process}", headers=h(admin_user), json={
        "service_id": sid, "resend_limit": 0, "regenerate_limit": 0, "ai_task": "drawing", "ai_action": action})
    assert r.status_code == 200, r.text
    return sid, process


async def test_人が手を入れた絵を元にAIが描き直すとき_人の手の範囲を必ずマスクで渡し_版がつながる(
        api, authz, admin, workers, fake_comfy):
    fake = fake_comfy(UploadingFakeComfy())
    a = user()
    ids = await new_work(api, a)
    wid = ids["work"]
    first = (await upload(api, wid, a, origin="imported", page_id=ids["page1"], source_note="作者の線画",
                          usage_terms=json.dumps(TERMS))).json()["id"]
    region = uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "add_protected_region", "id": region, "image_id": first,
                                   "polygon_px": [[0, 0], [20, 0], [20, 20], [0, 20]]})).status_code == 200
    # 人が外で手を入れた版（同じ大きさなので、前の版の人の手の範囲を引き継ぐ）
    second = (await upload(api, wid, a, origin="human_edited", page_id=ids["page1"], based_on_image_id=first,
                           data=png_bytes(shade=180))).json()["id"]
    sid, process = await make_redraw_service(api, admin)
    await workers.reload()
    base = {"process": process, "page_id": ids["page1"], "request": {
        "register": {"role": "panel_art", "page_id": ids["page1"]},
        "input_images": [{"node": "3", "input": "image", "image_id": second, "purpose": "source"}]}}
    # マスクを入れる所の無い依頼は受けない
    r = await api.post(f"/works/{wid}/jobs", headers=h(a), json=base)
    assert r.status_code == 422 and "人の手の範囲" in r.json()["detail"]
    # 依頼する側は prepared_inputs を書けない
    forged = {**base, "request": {**base["request"], "prepared_inputs": []}}
    assert (await api.post(f"/works/{wid}/jobs", headers=h(a), json=forged)).status_code == 422
    req = {**base, "request": {**base["request"], "protected_mask_input": {"node": "4", "input": "image"}}}
    r = await api.post(f"/works/{wid}/jobs", headers=h(a), json=req)
    assert r.status_code == 201, r.text
    prepared = r.json()["request"]["prepared_inputs"]
    assert [(p["purpose"], p.get("region_ids")) for p in prepared] == [("source", None), ("protected_mask", [region])]
    assert r.json()["request"]["register"]["based_on_image_id"] == second
    j = await until_status(api, wid, a, r.json()["id"], "done", "stopped")
    assert j["status"] == "done", j
    assert fake.uploads == ["up0.png", "up1.png"]
    assert (fake.prompt["3"]["inputs"]["image"], fake.prompt["4"]["inputs"]["image"]) == ("up0.png", "up1.png")
    (reg,) = j["result"]["registered"]
    chain = (await api.get(f"/works/{wid}/images/{reg['image_id']}/lineage", headers=h(a))).json()
    assert [v["origin"] for v in chain] == ["generated", "human_edited", "imported"]
    # サービスの利用規約が未記録なので、生成した版に印が立つ
    assert chain[0]["terms_missing"] is True and chain[0]["service"]["id"] == sid
    r = await api.patch(f"/services/{sid}", headers=h(admin), json={"usage_terms": TERMS | {"rights_holder": "利用者"}})
    assert r.status_code == 200, r.text
    chain = (await api.get(f"/works/{wid}/images/{reg['image_id']}/lineage", headers=h(a))).json()
    assert chain[0]["terms_missing"] is False and chain[0]["terms_from"] == "service"

    # 作画を「人が作りAIは検査だけ」にすると、作る依頼は受けない。検査の依頼は受ける
    assert (await op(api, wid, a, {"type": "set_ai_involvement", "task": "drawing",
                                   "mode": "human_makes_ai_checks"})).status_code == 200
    assert (await api.post(f"/works/{wid}/jobs", headers=h(a), json=req)).status_code == 409
    _, check_process = await make_redraw_service(api, admin, action="check")
    await workers.reload()
    r = await api.post(f"/works/{wid}/jobs", headers=h(a), json={**req, "process": check_process})
    assert r.status_code == 201, r.text
    # 検査の処理が絵を返しても、作画を任されていないので候補として登録しない（依頼は止まる）
    j = await until_status(api, wid, a, r.json()["id"], "done", "stopped")
    assert j["status"] == "stopped" and "絵の登録を断られた" in j["failure_detail"]
