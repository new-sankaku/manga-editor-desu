"""10.1・10.4 で足した操作と口の試験（compose の PostgreSQL・OpenFGA・Temporal を使う）。
どの操作も操作の窓口を通り、権限・ロック・人の手の印・取り消し・AIの関与が同じにかかることを確かめる。"""

import io
import json
import pathlib
import uuid

import pytest
from conftest import h, user, wait_for
from PIL import Image
from test_human_ai_interchange import ai_op, allow_ai, op, work_json
from test_human_edit_and_handover import image_dir, live, setup_name  # noqa: F401  (image_dir は fixture)

from v3server.server_settings import get_settings
from v3server.v3_error_types import FixedByPerson, Forbidden

ROOT = pathlib.Path(__file__).resolve().parents[3]
FONT_DIR = "/usr/share/fonts/opentype/ipafont-gothic"
FRAME_STYLE = {"line_width_mm": 0.5, "line_color": "#000000"}
TYPESETTING = {"line_spacing_ratio": 0.3, "line_break": "character", "tate_chu_yoko_max_digits": 2,
               "tate_chu_yoko_marks": True, "align": "start"}
PRINT = {"file_code": "T", "color_mode": "color", "dpi_by_color_mode": {"bilevel": 600, "grayscale": 350, "color": 350},
         "safe_area": {"top_mm": 5, "bottom_mm": 5, "gutter_mm": 5, "outer_mm": 5},
         "page_count_multiple": None, "page_count_scope": "episode"}


def png(w=40, h_=30, rgba=(200, 100, 50, 255)) -> bytes:
    b = io.BytesIO()
    Image.new("RGBA", (w, h_), rgba).save(b, format="PNG")
    return b.getvalue()


async def framed_page(api, a, texts=("1",)):
    """1ページに1つのコマ（基本枠いっぱいの枠）を作る。"""
    assert len(texts) == 1
    ids = await setup_name(api, a, texts=texts)
    p = await first_panel(api, ids["work"], a, ids["page1"])
    r = await op(api, ids["work"], a, {"type": "update_panel", "id": p["id"], "frame": {
        "polygon_mm": [[0, 0], [150, 0], [150, 220], [0, 220]], "bleeds": False}})
    assert r.status_code == 200, r.text
    return ids


async def first_panel(api, wid, a, page_id):
    return min(live((await work_json(api, wid, a))["panels"], page_id=page_id), key=lambda p: p["order"])


async def undo(api, wid, a, event_id):
    r = await api.post(f"/works/{wid}/events/{event_id}/undo", headers=h(a))
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- コマ枠


async def test_コマを分ける_合わせるは1つの操作で_1回で取り消せる(api, authz):
    a = user()
    ids = await framed_page(api, a, texts=("1",))
    wid = ids["work"]
    p = await first_panel(api, wid, a, ids["page1"])
    # 細すぎる分け方の閾値が無ければ分けない
    r = await op(api, wid, a, {"type": "split_panel", "panel_id": p["id"], "through_mm": [75, 110],
                               "direction": "horizontal"})
    assert r.status_code == 422 and "panel_short_side_min_mm" in r.text
    assert (await op(api, wid, a, {"type": "set_threshold", "key": "panel_short_side_min_mm", "value": {"value": 10},
                                   "source": "試験", "status": "unverified"})).status_code == 200
    new_id = uuid.uuid4().hex
    r = await op(api, wid, a, {"type": "split_panel", "panel_id": p["id"], "through_mm": [75, 110],
                               "direction": "horizontal", "new_panel_id": new_id})
    assert r.status_code == 200, r.text
    split_event = r.json()["event_id"]
    rows = live((await work_json(api, wid, a))["panels"], page_id=ids["page1"])
    assert len(rows) == 2 and all("frame" in x["human_hand_fields"] for x in rows)
    # 合わせて1つに戻す。合わせたのを取り消すと2つに戻る
    r = await op(api, wid, a, {"type": "merge_panels", "panel_ids": [p["id"], new_id]})
    assert r.status_code == 200, r.text
    assert len(live((await work_json(api, wid, a))["panels"], page_id=ids["page1"])) == 1
    await undo(api, wid, a, r.json()["event_id"])
    assert len(live((await work_json(api, wid, a))["panels"], page_id=ids["page1"])) == 2
    # 分けたのを1回で取り消す
    await undo(api, wid, a, split_event)
    rows = live((await work_json(api, wid, a))["panels"], page_id=ids["page1"])
    assert [x["id"] for x in rows] == [p["id"]] and rows[0]["frame"] == p["frame"]


# ---------------------------------------------------------------- トーン・図形・動かさない・仕上げ


async def test_トーンと図形_動かさない_まとめて戻す_AIが人の所に当たると判断待ち(api, authz):
    a = user()
    ids = await framed_page(api, a, texts=("1",))
    wid = ids["work"]
    p = await first_panel(api, wid, a, ids["page1"])
    tone, shape = uuid.uuid4().hex, uuid.uuid4().hex
    tone_spec = {"kind": "focus_lines", "target": {"kind": "panel", "panel_id": p["id"]}, "density": 0.4,
                 "line_count": 60, "center_mm": [70, 100], "inner_ratio": 0.3, "seed": 1}
    r0 = await op(api, wid, a, {"type": "add_page_item", "id": tone, "page_id": ids["page1"], "item_kind": "tone",
                                "spec": tone_spec, "box_mm": [0, 0, 150, 220], "stack_order": 0})
    assert r0.status_code == 200, r0.text
    bad = {**tone_spec, "target": {"kind": "panel", "panel_id": uuid.uuid4().hex}}
    assert (await op(api, wid, a, {"type": "add_page_item", "page_id": ids["page1"], "item_kind": "tone",
                                   "spec": bad, "box_mm": [0, 0, 1, 1], "stack_order": 1})).status_code in (404, 422)
    shape_spec = {"kind": "symbol", "symbol_name": "星", "points_mm": [[0, 0], [10, 0], [5, 8]],
                  "stroke": {"color": "#000000", "width_mm": 0.3}}
    r = await op(api, wid, a, {"type": "add_page_item", "id": shape, "page_id": ids["page1"], "item_kind": "shape",
                               "spec": shape_spec, "box_mm": [10, 10, 20, 18], "stack_order": 1,
                               "transform": {"rotation_deg": 15, "skew_x_deg": 10, "flip_h": True},
                               "adjustments": [{"kind": "brightness", "amount": 0.2}, {"kind": "blend", "mode": "multiply"}]})
    assert r.status_code == 200, r.text
    # まとめて戻す（1回で取り消せる）
    r = await op(api, wid, a, {"type": "reset_adjustments", "target_kind": "page_item", "id": shape})
    assert r.status_code == 200, r.text
    items = {x["id"]: x for x in (await work_json(api, wid, a))["page_items"]}
    assert items[shape]["adjustments"] == []
    await undo(api, wid, a, r.json()["event_id"])
    items = {x["id"]: x for x in (await work_json(api, wid, a))["page_items"]}
    assert len(items[shape]["adjustments"]) == 2

    # AIが人の置いた図形の不透明度を変えようとすると、変えずに判断待ちにする
    await allow_ai(api, wid, a, "finishing")
    await ai_op(authz, wid, a, {"type": "update_page_item", "id": shape, "opacity": 0.5})
    items = {x["id"]: x for x in (await work_json(api, wid, a))["page_items"]}
    assert items[shape]["opacity"] == 1.0
    held = (await api.get(f"/works/{wid}/held-changes", headers=h(a))).json()
    assert any(x["target_id"] == shape and x["field"] == "opacity" for x in held)

    # 動かさない：人もAIも変えられない。外せるのは人だけ
    r = await op(api, wid, a, {"type": "set_fixed", "target_kind": "page_item", "id": tone, "fixed": True})
    assert r.status_code == 200, r.text
    r2 = await op(api, wid, a, {"type": "update_page_item", "id": tone, "opacity": 0.5})
    assert r2.status_code == 409
    with pytest.raises(FixedByPerson):
        await ai_op(authz, wid, a, {"type": "update_page_item", "id": tone, "opacity": 0.5})
    with pytest.raises(Forbidden):
        await ai_op(authz, wid, a, {"type": "set_fixed", "target_kind": "page_item", "id": tone, "fixed": False})
    await undo(api, wid, a, r.json()["event_id"])
    assert (await op(api, wid, a, {"type": "update_page_item", "id": tone, "opacity": 0.5})).status_code == 200


async def test_新しい操作でも_AIの変更が人の手の所に当たるとその項目だけ判断待ちにし_取り消すと下がる(api, authz):
    a = user()
    ids = await framed_page(api, a, texts=("1",))
    wid = ids["work"]
    await allow_ai(api, wid, a, "finishing")
    shape = uuid.uuid4().hex
    spec = {"kind": "symbol", "symbol_name": "星", "points_mm": [[0, 0], [10, 0], [5, 8]],
            "stroke": {"color": "#000000", "width_mm": 0.3}}
    await ai_op(authz, wid, a, {"type": "add_page_item", "id": shape, "page_id": ids["page1"], "item_kind": "shape",
                                "spec": spec, "box_mm": [10, 10, 20, 18], "stack_order": 1})
    # 人が不透明度だけ直す（人の手の印が付く）
    assert (await op(api, wid, a, {"type": "update_page_item", "id": shape, "opacity": 0.8})).status_code == 200

    async def item():
        return next(x for x in (await work_json(api, wid, a))["page_items"] if x["id"] == shape)

    async def open_held():
        return [x for x in (await api.get(f"/works/{wid}/held-changes", headers=h(a))).json() if x["target_id"] == shape]

    visible = (await item())["visible"]
    ev = await ai_op(authz, wid, a, {"type": "update_page_item", "id": shape, "opacity": 0.3, "visible": not visible})
    assert [(x["target_table"], x["target_id"], x["field"]) for x in ev.held_changes] == [
        ("page_items", shape, "opacity")]
    (listed,) = (await api.get(f"/works/{wid}/events", headers=h(a), params={"after": ev.seq - 1})).json()
    assert listed["held_changes"] == ev.held_changes
    assert ((await item())["opacity"], (await item())["visible"]) == (0.8, not visible)
    (held,) = await open_held()
    assert (held["field"], held["proposed_value"], held["current_value"]) == ("opacity", 0.3, 0.8)

    # 取り消すと判断待ちは下がり、やり直すと開き直す
    r = await undo(api, wid, a, ev.id)
    assert (await item())["visible"] == visible and await open_held() == []
    await undo(api, wid, a, r["event_id"])
    assert (await item())["visible"] == (not visible) and [x["id"] for x in await open_held()] == [held["id"]]
    # 採らない
    r = await op(api, wid, a, {"type": "resolve_held_change", "id": held["id"], "decision": "reject"})
    assert r.status_code == 200, r.text
    assert await open_held() == [] and (await item())["opacity"] == 0.8


async def test_文字の書体_飾り_ルビ_角度_フキダシの形(api, authz):
    a = user()
    ids = await framed_page(api, a, texts=("ことば",))
    wid = ids["work"]
    (t,) = live((await work_json(api, wid, a))["text_items"], page_id=ids["page1"])
    body = {"type": "update_text_item", "id": t["id"], "font_family": "ipag",
            "decoration": {"fill": "#000000", "edge": {"color": "#ffffff", "ratio": 0.1}},
            "ruby": [{"start": 0, "end": 2, "text": "ルビ"}],
            "transform": {"rotation_deg": -10, "skew_y_deg": 5, "flip_v": False},
            "balloon_shape": {"kind": "custom", "outline_mm": [[0, 0], [20, 0], [20, 30], [0, 30]],
                              "line_width_mm": 0.3, "line_color": "#000000", "fill_color": "#ffffff"}}
    r = await op(api, wid, a, body)
    assert r.status_code == 200, r.text
    item = next(x for x in (await work_json(api, wid, a))["text_items"] if x["id"] == t["id"])
    assert item["font_family"] == "ipag" and item["ruby"][0]["text"] == "ルビ"
    assert {"font_family", "decoration", "ruby", "transform", "balloon_shape"} <= set(item["human_hand_fields"])
    # ルビの範囲が文字の外
    r = await op(api, wid, a, {"type": "update_text_item", "id": t["id"], "ruby": [{"start": 0, "end": 9, "text": "x"}]})
    assert r.status_code == 422
    # 描き文字にフキダシの形は持たせない
    r = await op(api, wid, a, {"type": "add_text_item", "panel_id": t["panel_id"], "item_kind": "drawn_sfx", "order": 1,
                               "text": "ド", "balloon_shape": body["balloon_shape"]})
    assert r.status_code == 422


# ---------------------------------------------------------------- ペン・消しゴム


def stroke(x0, x1, y=50.0, brush="pencil", **kw):
    pts = [[x0 + (x1 - x0) * i / 10, y, 0.5, float(i)] for i in range(11)]
    return {"brush": brush, "points": pts, "width_mm": 0.5, "color": "#000000", "opacity": 1.0} | kw


async def test_ペンの線は1本ずつの物で_選んで変え_線の消しゴムで分かれ_控えの古さが分かる(api, authz, image_dir):
    a = user()
    ids = await framed_page(api, a, texts=("1",))
    wid = ids["work"]
    p = await first_panel(api, wid, a, ids["page1"])
    layer = uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "add_panel_layer", "id": layer, "panel_id": p["id"], "role": "human_hand",
                                   "stack_order": 0})).status_code == 200
    r = await op(api, wid, a, {"type": "add_pen_strokes", "layer_id": layer,
                               "strokes": [stroke(10, 30), stroke(10, 30, y=60, brush="crayon", seed=7)]})
    assert r.status_code == 200, r.text
    w = await work_json(api, wid, a)
    strokes = live(w["pen_strokes"], layer_id=layer)
    assert len(strokes) == 2 and all("points" in s["human_hand_fields"] for s in strokes)
    lay = next(x for x in w["panel_layers"] if x["id"] == layer)
    assert lay["stroke_revision"] == 1
    # AIは線を描けない
    with pytest.raises(Forbidden):
        await ai_op(authz, wid, a, {"type": "add_pen_strokes", "layer_id": layer, "strokes": [stroke(0, 1)]})
    # 2本まとめて動かし、色を変える（1回で取り消せる）
    r = await op(api, wid, a, {"type": "update_pen_strokes", "ids": [s["id"] for s in strokes], "move_mm": [5, 0],
                               "color": "#ff0000"})
    assert r.status_code == 200, r.text
    moved = live((await work_json(api, wid, a))["pen_strokes"], layer_id=layer)
    assert all(s["color"] == "#ff0000" and s["points"][0][0] == 15 for s in moved)
    await undo(api, wid, a, r.json()["event_id"])
    back = live((await work_json(api, wid, a))["pen_strokes"], layer_id=layer)
    assert all(s["color"] == "#000000" and s["points"][0][0] == 10 for s in back)
    # 触れた所だけ消す：1本目が2本に分かれ、2本目は触れていないので残る
    r = await op(api, wid, a, {"type": "erase_pen_strokes", "layer_id": layer, "mode": "touched",
                               "path_mm": [[20, 45], [20, 55]], "width_mm": 1})
    assert r.status_code == 200, r.text
    after = live((await work_json(api, wid, a))["pen_strokes"], layer_id=layer)
    assert len(after) == 3
    await undo(api, wid, a, r.json()["event_id"])
    assert len(live((await work_json(api, wid, a))["pen_strokes"], layer_id=layer)) == 2

    # 控え：古い版から描いた控えは受けない。今の版なら層の絵になる
    w = await work_json(api, wid, a)
    rev = next(x for x in w["panel_layers"] if x["id"] == layer)["stroke_revision"]
    placement = json.dumps({"crop_px": [0, 0, 40, 30], "dest_box_mm": [0, 0, 40, 30]})
    files = {"image": ("c.png", png(), "image/png")}
    r = await api.post(f"/works/{wid}/layers/{layer}/stroke-cache", headers=h(a), files=files,
                       data={"stroke_revision": str(rev - 1), "placement": placement})
    assert r.status_code == 422
    r = await api.post(f"/works/{wid}/layers/{layer}/stroke-cache", headers=h(a), files=files,
                       data={"stroke_revision": str(rev), "placement": placement})
    assert r.status_code == 200, r.text
    lay = next(x for x in (await work_json(api, wid, a))["panel_layers"] if x["id"] == layer)
    assert lay["image_id"] == r.json()["image_id"] and lay["image_stroke_revision"] == rev
    # 線を変えると控えは古くなり、その絵を AIへ渡す依頼は止まる
    assert (await op(api, wid, a, {"type": "add_pen_strokes", "layer_id": layer,
                                   "strokes": [stroke(0, 5)]})).status_code == 200
    lay = next(x for x in (await work_json(api, wid, a))["panel_layers"] if x["id"] == layer)
    assert lay["stroke_revision"] == rev + 1 and lay["image_stroke_revision"] == rev
    # 線を持つ層の絵は、控えの口（set_stroke_cache）でだけ替える
    other = await api.post(f"/works/{wid}/images", headers=h(a), files={"image": ("o.png", png(), "image/png")},
                           data={"role": "human_hand", "origin": "human_drawn"})
    assert other.status_code == 201, other.text
    r = await op(api, wid, a, {"type": "update_panel_layer", "id": layer, "image_id": other.json()["id"]})
    assert r.status_code == 422


async def test_画素の消しゴムは新しい版と人の手の範囲を作る(api, authz, image_dir):
    a = user()
    ids = await framed_page(api, a, texts=("1",))
    wid = ids["work"]
    p = await first_panel(api, wid, a, ids["page1"])
    r = await api.post(f"/works/{wid}/panels/{p['id']}/image", headers=h(a),
                       files={"image": ("a.png", png(), "image/png")}, data={"origin": "human_drawn"})
    assert r.status_code == 201, r.text
    base = r.json()["id"]
    r = await api.post(f"/works/{wid}/panels/{p['id']}/erase-pixels", headers=h(a),
                       data={"strokes": json.dumps([{"points": [[10, 10], [20, 10]], "width_px": 4}])})
    assert r.status_code == 200, r.text
    new = r.json()["image_id"]
    lineage = (await api.get(f"/works/{wid}/images/{new}/lineage", headers=h(a))).json()
    assert base in json.dumps(lineage)
    regions = (await api.get(f"/works/{wid}/images/{new}/protected-regions", headers=h(a))).json()
    assert len(regions) == 1 and regions[0]["mask_sha256"]
    panel = await first_panel(api, wid, a, ids["page1"])
    assert panel["image_id"] == new


# ---------------------------------------------------------------- 赤入れ・企画・設定資料・探す・設定


async def test_赤入れ_企画_設定資料_探す_置き換え_利用者の設定(api, authz):
    a = user()
    ids = await framed_page(api, a, texts=("猫が来た",))
    wid = ids["work"]
    p = await first_panel(api, wid, a, ids["page1"])
    ann = uuid.uuid4().hex
    r = await op(api, wid, a, {"type": "add_annotation", "id": ann, "page_id": ids["page1"], "panel_id": p["id"],
                               "region_mm": [[0, 0], [10, 0], [10, 10]], "body": "猫の顔を直す", "about_task": "drawing"})
    assert r.status_code == 200, r.text
    assert (await op(api, wid, a, {"type": "update_annotation", "id": ann, "status": "resolved"})).status_code == 200

    assert (await op(api, wid, a, {"type": "set_work_plan", "synopsis": "猫が町を歩く", "audience": "子ども",
                                   "exclusions": ["流血"]})).status_code == 200
    cat = uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "add_material_entry", "id": cat, "kind": "character", "name": "猫",
                                   "traits": "白い猫", "generation": {"prompt": "猫", "seed": 3}})).status_code == 200
    # AIが足した設定資料は案
    ai_entry = uuid.uuid4().hex
    await ai_op(authz, wid, a, {"type": "add_material_entry", "id": ai_entry, "kind": "character", "name": "犬"})
    mats = {m["id"]: m for m in (await work_json(api, wid, a))["material_entries"]}
    assert mats[cat]["proposal_state"] == "adopted" and mats[ai_entry]["proposal_state"] == "proposed"

    found = (await api.get(f"/works/{wid}/search", headers=h(a), params={"q": "猫"})).json()
    tables = {x["table"] for x in found}
    assert {"text_items", "material_entries", "work_plans", "annotation_items"} <= tables
    r = await op(api, wid, a, {"type": "replace_text", "find": "猫", "replace": "狐", "kinds": ["text", "name", "setting"]})
    assert r.status_code == 200, r.text
    assert not [x for x in (await api.get(f"/works/{wid}/search", headers=h(a), params={"q": "猫"})).json()
                if x["table"] != "annotation_items"]
    await undo(api, wid, a, r.json()["event_id"])
    assert len((await api.get(f"/works/{wid}/search", headers=h(a), params={"q": "猫"})).json()) == len(found)

    # 利用者ごとの設定は自分の物だけ
    r = await api.put("/me/settings", headers=h(a), json={"language": "ja", "autosave": True,
                                                          "autosave_interval_seconds": 60})
    assert r.status_code == 200 and r.json()["language"] == "ja"
    assert (await api.get("/me/settings", headers=h(user()))).json()["language"] is None


# ---------------------------------------------------------------- 書き出しと PSD の戻し


@pytest.fixture
def export_env(monkeypatch, tmp_path, image_dir):
    s = get_settings()
    monkeypatch.setattr(s, "export_dir", str(tmp_path / "exports"))
    monkeypatch.setattr(s, "font_dir", FONT_DIR)
    monkeypatch.setattr(s, "node_executable", "/opt/node22/bin/node")
    monkeypatch.setattr(s, "text_render_script", str(ROOT / "psd_writer" / "render_text.js"))
    monkeypatch.setattr(s, "psd_writer_script", str(ROOT / "psd_writer" / "write_layered_psd.js"))
    return tmp_path


async def ready_page(api, a):
    ids = await framed_page(api, a, texts=("あ",))
    wid = ids["work"]
    p = await first_panel(api, wid, a, ids["page1"])
    assert (await op(api, wid, a, {"type": "set_work_settings",
                                   "preferences": {"frame_style": FRAME_STYLE, "typesetting": TYPESETTING,
                                                   "print": PRINT}})).status_code == 200
    r = await api.post(f"/works/{wid}/panels/{p['id']}/image", headers=h(a),
                       files={"image": ("a.png", png(), "image/png")}, data={"origin": "human_drawn"})
    assert r.status_code == 201, r.text
    p = {**p, "image_id": r.json()["id"]}
    frame = p["frame"]["polygon_mm"]
    xs, ys = [q[0] for q in frame], [q[1] for q in frame]
    assert (await op(api, wid, a, {"type": "update_panel", "id": p["id"], "image_placement": {
        "crop_px": [0, 0, 40, 30], "dest_box_mm": [min(xs), min(ys), max(xs), max(ys)]}})).status_code == 200
    (t,) = live((await work_json(api, wid, a))["text_items"], page_id=ids["page1"])
    r = await op(api, wid, a, {"type": "update_text_item", "id": t["id"], "font_family": "ipag", "font_size_pt": 12,
                               "box_mm": [min(xs) + 5, min(ys) + 5, min(xs) + 20, min(ys) + 40],
                               "decoration": {"fill": "#000000"}})
    assert r.status_code == 200, r.text
    return ids, p, t


@pytest.mark.skipif(not pathlib.Path(FONT_DIR, "ipag.ttf").exists(), reason="試験の書体が無い")
async def test_書き出し_PNG_PDF_PSDと_直したPSDの戻し(api, authz, workers, export_env):
    a = user()
    ids, p, t = await ready_page(api, a)
    wid = ids["work"]

    async def export(fmt, **kw):
        r = await api.post(f"/works/{wid}/exports", headers=h(a),
                           json={"format": fmt, "page_ids": [ids["page1"]], "dpi": 40} | kw)
        assert r.status_code == 201, r.text
        rid = r.json()["id"]

        async def done():
            got = (await api.get(f"/works/{wid}/exports/{rid}", headers=h(a))).json()
            return got if got["status"] in ("done", "failed") else None

        return await wait_for(done, timeout=60)

    png_run = await export("png", paper_mm=[200, 280])
    assert png_run["status"] == "done", png_run["detail"]
    f = await api.get(f"/works/{wid}/exports/{png_run['id']}/files/{png_run['outputs'][0]['file']}", headers=h(a))
    assert Image.open(io.BytesIO(f.content)).size == (round(200 / 25.4 * 40), round(280 / 25.4 * 40))
    pdf_run = await export("pdf")
    assert pdf_run["status"] == "done", pdf_run["detail"]
    # 紙がページより小さければ止める（理由を残す）
    small = await export("png", paper_mm=[100, 100])
    assert small["status"] == "failed" and "小さい" in small["detail"]

    psd_run = await export("psd")
    assert psd_run["status"] == "done", psd_run["detail"]
    assert "画素" in psd_run["note"]
    out = psd_run["outputs"][0]
    markers = {la["marker"] for la in out["layers"]}
    assert f"{p['id']}-image" in markers and t["id"] in markers and f"{ids['page1']}-paper" in markers

    # 直した PSD：コマの絵の画素を変える・文字の層の画素を変える・コマのグループに描き足す
    from psd_tools import PSDImage  # 読み戻して、同じ層を ag-psd で書き直す

    data = (await api.get(f"/works/{wid}/exports/{psd_run['id']}/files/{out['file']}", headers=h(a))).content
    psd = PSDImage.open(io.BytesIO(data))
    tmp = export_env / "edit"
    tmp.mkdir()

    def to_req(layers):
        res = []
        for i, la in enumerate(layers):
            if la.is_group():
                res.append({"name": la.name, "children": to_req(list(la)), "opacity": 1, "blend_mode": "normal",
                            "hidden": False})
                continue
            img = la.topil().convert("RGBA")
            if la.name.endswith((f"[{p['id']}-image]", f"[{t['id']}]")):
                img.putpixel((img.width // 2, img.height // 2), (1, 2, 3, 255))
            path = tmp / f"{uuid.uuid4().hex}.png"
            img.save(path)
            res.append({"name": la.name, "png_path": str(path), "left": la.left, "top": la.top, "opacity": 1,
                        "blend_mode": "normal", "hidden": False})
        return res

    layers = to_req(list(psd))
    group = next(x for x in layers if x["name"].endswith(f"[{p['id']}]"))
    Image.new("RGBA", (5, 5), (9, 9, 9, 255)).save(tmp / "new.png")
    group["children"].append({"name": "描き足し", "png_path": str(tmp / "new.png"), "left": group["children"][0]["left"],
                              "top": group["children"][0]["top"], "opacity": 1, "blend_mode": "normal", "hidden": False})
    from v3server.print_export.layered_psd_request import write_layered_psd

    write_layered_psd({"width": psd.width, "height": psd.height, "composite_png": None,
                       "output_path": str(tmp / "edited.psd"), "layers": layers},
                      "/opt/node22/bin/node", ROOT / "psd_writer" / "write_layered_psd.js", 60)
    r = await api.post(f"/works/{wid}/exports/{psd_run['id']}/pages/{ids['page1']}/psd", headers=h(a),
                       files={"psd": ("edited.psd", (tmp / "edited.psd").read_bytes(), "image/vnd.adobe.photoshop")})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["matches"]["changed"] >= 1 and res["matches"]["new"] == 1
    w = await work_json(api, wid, a)
    panel = next(x for x in w["panels"] if x["id"] == p["id"])
    assert panel["image_id"] != p["image_id"] and "image_id" in panel["human_hand_fields"]
    hand = live(w["panel_layers"], panel_id=p["id"], role="human_hand")
    assert len(hand) == 1
    # 文字の層の画素が変わった：文字の値は変えず、判断待ち（打ち直す・絵として採る・捨てる）
    text_held = [x for x in res["held"] if x["kind"] == "psd_text_pixels"]
    assert text_held and text_held[0]["choices"] == ["retype", "adopt_as_image", "discard"]
    assert next(x for x in w["text_items"] if x["id"] == t["id"])["text"] == "あ"
    r = await op(api, wid, a, {"type": "resolve_held_change", "id": text_held[0]["id"], "decision": "choose",
                               "choice": "retype", "params": {"text": "い"}})
    assert r.status_code == 200, r.text
    assert next(x for x in (await work_json(api, wid, a))["text_items"] if x["id"] == t["id"])["text"] == "い"
    # 選んだのを取り消すと、文字が戻り判断待ちに戻る
    await undo(api, wid, a, r.json()["event_id"])
    assert next(x for x in (await work_json(api, wid, a))["text_items"] if x["id"] == t["id"])["text"] == "あ"
    # 戻しは1回で取り消せる（コマの絵が前の版に戻り、描き足しの層が抜け、判断待ちは下げる）
    await undo(api, wid, a, res["event_id"])
    w = await work_json(api, wid, a)
    assert next(x for x in w["panels"] if x["id"] == p["id"])["image_id"] == p["image_id"]
    assert not live(w["panel_layers"], panel_id=p["id"], role="human_hand")
    held = (await api.get(f"/works/{wid}/held-changes", headers=h(a))).json()
    assert not [x for x in held if x["id"] == text_held[0]["id"] and x["status"] == "open"]
