"""原稿として出す形（V3点検の結果 §3）の試験（compose の PostgreSQL・OpenFGA・Temporal を使う）。
ページの並べ替えと見開きの操作、ページの種類・色の種類・解像度、見開き・ノンブル・2階調の書き出し、入稿前の確かめ。"""

import io
import pathlib
import uuid

import numpy as np
import pypdf
import pytest
from conftest import h, new_work, user, wait_for
from PIL import Image
from test_human_ai_interchange import PAGE_SPEC, ai_op, op, work_json
from test_human_edit_and_handover import image_dir, live, upload  # noqa: F401  (image_dir は fixture)
from test_human_tools_and_finishing import FRAME_STYLE, TYPESETTING, edit_psd, export_env, undo  # noqa: F401

from v3server.v3_error_types import HumanHandProtected

FONT_DIR = "/usr/share/fonts/opentype/ipafont-gothic"
needs_font = pytest.mark.skipif(not pathlib.Path(FONT_DIR, "ipag.ttf").exists(), reason="試験の書体が無い")
DPI = 40
PRINT = {"file_code": "BK", "color_mode": "bilevel", "dpi_by_color_mode": {"bilevel": DPI, "grayscale": DPI,
                                                                             "color": DPI},
         "bilevel": {"threshold": 128, "pdf_codec": "ccitt_g4",
                     "image_screen": {"lines_per_inch": 10, "angle_deg": 45, "dot_shape": "round"}},
         "safe_area": {"top_mm": 10, "bottom_mm": 10, "gutter_mm": 12, "outer_mm": 8},
         "page_count_multiple": 4, "page_count_scope": "episode"}
NOMBRE = {"font_family": "ipag", "font_size_pt": 9, "hidden_font_size_pt": 6, "color": "#000000", "start_number": 1,
          "numbering_scope": "episode",
          "position": {"vertical": "bottom", "horizontal": "outer", "edge_mm": 5, "side_mm": 5},
          "hidden_position": {"bottom_mm": 3, "gutter_mm": 3},
          "display_by_kind": {"cover": "none", "color_page": "hidden", "body": "visible", "blank": "hidden"}}


async def book(api, a, pages=4):
    """右から読む・1ページ目が右の、pages ページの話。入稿の設定とノンブルの設定を入れる。"""
    ids = await new_work(api, a)
    wid = ids["work"]
    pids = [ids["page1"], ids["page2"]]
    for n in range(3, pages + 1):
        pid = uuid.uuid4().hex
        assert (await op(api, wid, a, {"type": "add_page", "id": pid, "episode_id": ids["episode"],
                                       "number": n})).status_code == 200
        pids.append(pid)
    r = await op(api, wid, a, {"type": "set_work_settings", "page_spec": PAGE_SPEC, "first_page_is_left": False,
                               "preferences": {"frame_style": FRAME_STYLE, "typesetting": TYPESETTING,
                                               "print": PRINT, "nombre": NOMBRE}})
    assert r.status_code == 200, r.text
    return wid, ids, pids


def numbers(w, pids):
    by = {p["id"]: p["number"] for p in w["pages"]}
    return [by[p] for p in pids]


async def test_並べ替えと見開きの操作_組が崩れるときは止め_取り消せる(api, authz):
    a = user()
    wid, ids, (p1, p2, p3, p4) = await book(api, a)
    # 並べ替え：番号を1から振り直し、取り消すと前の番号に戻る
    r = await op(api, wid, a, {"type": "reorder_pages", "episode_id": ids["episode"], "page_ids": [p2, p1, p3, p4]})
    assert r.status_code == 200, r.text
    assert numbers(await work_json(api, wid, a), [p2, p1, p3, p4]) == [1, 2, 3, 4]
    await undo(api, wid, a, r.json()["event_id"])
    assert numbers(await work_json(api, wid, a), [p1, p2, p3, p4]) == [1, 2, 3, 4]
    # 全部のページを渡さない並べ替えは止める
    assert (await op(api, wid, a, {"type": "reorder_pages", "episode_id": ids["episode"],
                                   "page_ids": [p2, p1]})).status_code == 422

    # 見開き：右から読む・1ページ目が右なので 1-2 は組になり、2-3（前が左・後ろが右）はならない
    sid = uuid.uuid4().hex
    r = await op(api, wid, a, {"type": "add_spread", "id": sid, "first_page_id": p1, "second_page_id": p2})
    assert r.status_code == 200, r.text
    r2 = await op(api, wid, a, {"type": "add_spread", "first_page_id": p2, "second_page_id": p3})
    assert r2.status_code == 422 and "前のページが左" in r2.text
    # 見開きの組が崩れる並べ替えは止める
    r2 = await op(api, wid, a, {"type": "reorder_pages", "episode_id": ids["episode"], "page_ids": [p1, p3, p2, p4]})
    assert r2.status_code == 422 and "見開き" in r2.text
    # 見開きを解く・取り消して戻す
    r2 = await op(api, wid, a, {"type": "set_removed", "target_kind": "spread", "id": sid, "removed": True})
    assert r2.status_code == 200, r2.text
    assert live((await work_json(api, wid, a))["spreads"]) == []
    await undo(api, wid, a, r2.json()["event_id"])
    assert [s["id"] for s in live((await work_json(api, wid, a))["spreads"])] == [sid]

    # ページの種類・色の種類・解像度・ノンブルの出し方は人だけが変える
    r = await op(api, wid, a, {"type": "update_page", "id": p1, "page_kind": "color_page", "color_mode": "color",
                               "dpi": 350, "nombre_display": "hidden"})
    assert r.status_code == 200, r.text
    page = next(p for p in (await work_json(api, wid, a))["pages"] if p["id"] == p1)
    assert (page["page_kind"], page["color_mode"], page["dpi"], page["nombre_display"]) == \
        ("color_page", "color", 350, "hidden")
    with pytest.raises(HumanHandProtected):
        await ai_op(authz, wid, a, {"type": "update_page", "id": p2, "color_mode": "grayscale"})


async def _export(api, wid, a, body):
    r = await api.post(f"/works/{wid}/exports", headers=h(a), json=body)
    assert r.status_code == 201, r.text
    rid = r.json()["id"]

    async def done():
        got = (await api.get(f"/works/{wid}/exports/{rid}", headers=h(a))).json()
        return got if got["status"] in ("done", "failed") else None

    return await wait_for(done, timeout=90)


async def _file(api, wid, a, run, name):
    r = await api.get(f"/works/{wid}/exports/{run['id']}/files/{name}", headers=h(a))
    assert r.status_code == 200, r.text
    return r.content


@needs_font
async def test_見開きと2階調とノンブルの書き出し_入稿前の確かめ(api, authz, workers, export_env):
    a = user()
    wid, ids, (p1, p2, p3, p4) = await book(api, a)
    for p in (p1, p2, p3, p4):
        assert (await op(api, wid, a, {"type": "update_page", "id": p, "page_kind": "body"})).status_code == 200
    sid = uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "add_spread", "id": sid, "first_page_id": p1,
                                   "second_page_id": p2})).status_code == 200
    # 見開きにまたがる灰色の絵（2階調では網点になる）
    buf = io.BytesIO()
    Image.new("RGBA", (600, 180), (128, 128, 128, 255)).save(buf, format="PNG")
    r = await upload(api, wid, a, data=buf.getvalue())
    assert r.status_code == 201, r.text
    spread_w = 2 * PAGE_SPEC["trim_width_mm"]
    ox = (PAGE_SPEC["trim_width_mm"] - PAGE_SPEC["frame_width_mm"]) / 2
    oy = (PAGE_SPEC["trim_height_mm"] - PAGE_SPEC["frame_height_mm"]) / 2
    r = await op(api, wid, a, {"type": "update_spread", "id": sid, "image_id": r.json()["id"], "image_placement": {
        "crop_px": [0, 0, 600, 180], "dest_box_mm": [-ox, -oy, spread_w - ox, 100 - oy]}})
    assert r.status_code == 200, r.text

    # 見開きの出し方が決まっていなければ止める
    run = await _export(api, wid, a, {"format": "png", "page_ids": [p1, p2, p3, p4]})
    assert run["status"] == "failed" and "spread_output" in run["detail"]

    run = await _export(api, wid, a, {"format": "png", "page_ids": [p1, p2, p3, p4], "spread_output": "both"})
    assert run["status"] == "done", run["detail"]
    files = {o["file"]: o for o in run["outputs"]}
    assert set(files) == {"BK_01_001-002.png", "BK_01_001.png", "BK_01_002.png", "BK_01_003.png", "BK_01_004.png"}
    assert all(o["dpi"] == DPI and o["color_mode"] == "bilevel" for o in run["outputs"])
    joined = Image.open(io.BytesIO(await _file(api, wid, a, run, "BK_01_001-002.png")))
    single = Image.open(io.BytesIO(await _file(api, wid, a, run, "BK_01_003.png")))
    assert joined.mode == single.mode == "1"
    k = DPI / 25.4
    assert joined.width == round((spread_w + 2 * PAGE_SPEC["bleed_mm"]) * k)
    assert single.size == (round((PAGE_SPEC["trim_width_mm"] + 6) * k), round((PAGE_SPEC["trim_height_mm"] + 6) * k))
    # 3ページ目（右のページ）のノンブル：小口（右）の下に黒い画素があり、上には無い
    black = np.asarray(single.convert("L")) == 0
    assert black[-round(20 * k):, -round(30 * k):].any() and not black[:round(20 * k), :].any()

    # PDF は見開きを分けて出す（4ページ）。PSD は見開きを1枚で出し、直した PSD を2ページ分まとめて戻せる
    pdf_run = await _export(api, wid, a, {"format": "pdf", "page_ids": [p1, p2, p3, p4], "spread_output": "split"})
    assert pdf_run["status"] == "done", pdf_run["detail"]
    pdf = pypdf.PdfReader(io.BytesIO(await _file(api, wid, a, pdf_run, "BK.pdf")))
    assert len(pdf.pages) == 4
    bad = await _export(api, wid, a, {"format": "pdf", "page_ids": [p1, p2], "spread_output": "joined"})
    assert bad["status"] == "failed" and "split" in bad["detail"]
    # 右のページ（p1。1ページ目が右）に絵の入ったコマを置く
    panel1 = uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "add_panel", "id": panel1, "page_id": p1, "order": 0, "frame": {
        "polygon_mm": [[10, 10], [60, 10], [60, 60], [10, 60]], "bleeds": False}})).status_code == 200
    buf = io.BytesIO()
    Image.new("RGBA", (50, 50), (200, 200, 200, 255)).save(buf, format="PNG")
    r = await api.post(f"/works/{wid}/panels/{panel1}/image", headers=h(a),
                       files={"image": ("a.png", buf.getvalue(), "image/png")}, data={"origin": "human_drawn"})
    assert r.status_code == 201, r.text
    panel_image = r.json()["id"]
    assert (await op(api, wid, a, {"type": "update_panel", "id": panel1, "image_placement": {
        "crop_px": [0, 0, 50, 50], "dest_box_mm": [10, 10, 60, 60]}})).status_code == 200
    psd_run = await _export(api, wid, a, {"format": "psd", "page_ids": [p1, p2], "spread_output": "joined"})
    assert psd_run["status"] == "done", psd_run["detail"]
    out = psd_run["outputs"][0]
    assert out["page_ids"] == [p1, p2] and out["left_page_id"] == p2
    data = (await _file(api, wid, a, psd_run, out["file"]))
    # 直した PSD：右のページのコマの絵と、見開きの絵の画素を変え、右のページのコマに描き足す
    edited = edit_psd(data, export_env / "edit-spread", (f"[{panel1}-image]", f"[{sid}-image]"),
                      add_to_group=f"[{panel1}]")
    r = await api.post(f"/works/{wid}/exports/{psd_run['id']}/pages/{p2}/psd", headers=h(a),
                       files={"psd": ("s.psd", edited, "image/vnd.adobe.photoshop")})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["matches"]["changed"] == 2 and res["matches"]["new"] == 1, res["matches"]
    w = await work_json(api, wid, a)
    panel = next(x for x in w["panels"] if x["id"] == panel1)
    assert panel["image_id"] != panel_image
    # 右のページの絵は、右のページの基本枠の mm に戻る（見開きの左の端からの mm ではない）
    box = panel["image_placement"]["dest_box_mm"]
    assert -1 < box[0] < 15 and box[2] < PAGE_SPEC["frame_width_mm"], box
    hand = [x for x in w["panel_layers"] if x["panel_id"] == panel1 and x["role"] == "human_hand" and not x["removed"]]
    assert len(hand) == 1 and hand[0]["page_id"] == p1
    # 見開きの絵はどちらのページの物でもないので判断待ち（層の真ん中の側のページに付く）
    (spread_held,) = [x for x in res["held"] if x["kind"] == "psd_unmatched_layer"]
    assert spread_held["payload"]["marker"] == f"{sid}-image"
    # 2ページ分を1回で取り消せる
    await undo(api, wid, a, res["event_id"])
    w = await work_json(api, wid, a)
    assert next(x for x in w["panels"] if x["id"] == panel1)["image_id"] == panel_image
    assert not [x for x in w["panel_layers"] if x["panel_id"] == panel1 and x["role"] == "human_hand"
                and not x["removed"]]
    # 見開きを外した後のページ全体の確かめのため、描き足したコマは抜く
    assert (await op(api, wid, a, {"type": "set_removed", "target_kind": "panel", "id": panel1,
                                   "removed": True})).status_code == 200

    # 入稿前の確かめ：揃っていれば error は無い
    r = await api.post(f"/works/{wid}/preflight", headers=h(a), json={})
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["ok"], got["issues"]
    # ページ数が倍数でない・種類の決まっていないページ・安全線の外の文字・箱に入らない文字
    p5 = uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "add_page", "id": p5, "episode_id": ids["episode"],
                                   "number": 5})).status_code == 200
    panel = uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "add_panel", "id": panel, "page_id": p3, "order": 1})).status_code == 200
    r = await op(api, wid, a, {"type": "add_text_item", "panel_id": panel, "item_kind": "balloon",
                               "order": 0, "text": "あいうえおかきくけこさしすせそ", "font_family": "ipag",
                               "font_size_pt": 12, "writing_direction": "vertical", "box_mm": [-10, 0, 0, 20],
                               "decoration": {"fill": "#000000"}})
    assert r.status_code == 200, r.text
    got = (await api.post(f"/works/{wid}/preflight", headers=h(a), json={})).json()
    kinds = {(i["kind"], i["page_id"]) for i in got["issues"] if i["severity"] == "error"}
    assert ("page_count", None) in kinds and ("page_kind", p5) in kinds
    assert ("safe_area", p3) in kinds and ("text_overflow", p3) in kinds
    text_issue = next(i for i in got["issues"] if i["kind"] == "safe_area")
    assert text_issue["location"]["table"] == "text_items"
    # 色（decoration.fill）の無い文字（取り込んだ文字・古い文字）：色を補わず、どの文字かを付けて error にする
    panel4 = uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "add_panel", "id": panel4, "page_id": p4, "order": 1})).status_code == 200
    r = await op(api, wid, a, {"type": "add_text_item", "panel_id": panel4, "item_kind": "balloon", "order": 0,
                               "text": "いろなし", "font_family": "ipag", "font_size_pt": 12,
                               "writing_direction": "vertical", "box_mm": [20, 20, 40, 60]})
    assert r.status_code == 200, r.text
    got = (await api.post(f"/works/{wid}/preflight", headers=h(a), json={})).json()
    color = [i for i in got["issues"] if i["kind"] == "text_color"]
    assert len(color) == 1 and color[0]["severity"] == "error" and color[0]["page_id"] == p4
    assert color[0]["location"]["table"] == "text_items" and "decoration.fill" in color[0]["message"]
    assert "いろなし" in color[0]["message"]
