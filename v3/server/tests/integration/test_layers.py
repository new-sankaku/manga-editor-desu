"""層（コマの絵の層・トーンと図形のページの層）の試験（compose の PostgreSQL・OpenFGA・Temporal を使う）。

順・見せるか・動かさない（固定）・不透明度を変え、1つずつ取り消せること、人の手の印で AI の変更を判断待ちに置くこと、
書き出しの絵が見せるか・順に従うことを確かめる。書き出し（Temporal と描画を通す）だけ full の組、ほかは速い組（fast）。
絵は 4×4 画素、書き出しは 40dpi。
"""

import io
import uuid

import numpy as np
import pytest
from conftest import h, user
from PIL import Image
from test_human_ai_interchange import PAGE_SPEC, ai_op, allow_ai, op, work_json
from test_human_edit_and_handover import image_dir, upload  # noqa: F401  (image_dir は fixture)
from test_human_tools_and_finishing import export_env, undo  # noqa: F401  (export_env は fixture)
from test_print_manuscript_flow import DPI, _export, _file, book, needs_font

from v3server.v3_error_types import HumanHandProtected

RED, BLUE = (220, 20, 20, 255), (20, 20, 220, 255)
# 層を置く所（基本枠の mm）。コマは基本枠いっぱい
BOX = [20.0, 20.0, 100.0, 100.0]


def solid(rgba) -> bytes:
    b = io.BytesIO()
    Image.new("RGBA", (4, 4), rgba).save(b, format="PNG")
    return b.getvalue()


def place(box=BOX):
    return {"crop_px": [0, 0, 4, 4], "dest_box_mm": box}


async def layered_page(api, a):
    """1ページ・1コマ（基本枠いっぱい）に、赤（下）と青（上）の層を重ねる。"""
    wid, ids, (p1, *_) = await book(api, a, pages=4)
    for pid in ids["page1"], ids["page2"]:
        r = await op(api, wid, a, {"type": "update_page", "id": pid, "page_kind": "body", "color_mode": "color"})
        assert r.status_code == 200, r.text
    panel = uuid.uuid4().hex
    r = await op(api, wid, a, {"type": "add_panel", "id": panel, "page_id": p1, "order": 1, "frame": {
        "polygon_mm": [[0, 0], [150, 0], [150, 220], [0, 220]], "bleeds": False}})
    assert r.status_code == 200, r.text
    layers = {}
    for name, rgba, order in (("red", RED, 1), ("blue", BLUE, 2)):
        img = (await upload(api, wid, a, data=solid(rgba), role="tone", panel_id=panel)).json()["id"]
        layers[name] = uuid.uuid4().hex
        r = await op(api, wid, a, {"type": "add_panel_layer", "id": layers[name], "panel_id": panel, "role": "tone",
                                   "image_id": img, "stack_order": order, "placement": place()})
        assert r.status_code == 200, r.text
    return wid, p1, panel, layers


async def layer(api, wid, a, lid):
    return next(x for x in (await work_json(api, wid, a))["panel_layers"] if x["id"] == lid)


async def item(api, wid, a, iid):
    return next(x for x in (await work_json(api, wid, a))["page_items"] if x["id"] == iid)


async def test_コマの層の順_見せるか_不透明度_固定をそれぞれ変えて取り消せる(api, authz, image_dir):  # noqa: F811
    a = user()
    wid, _, _, ly = await layered_page(api, a)
    red = ly["red"]
    cases = [({"stack_order": 3}, ("stack_order", 1, 3)),
             ({"visible": False}, ("visible", True, False)),
             ({"opacity": 0.25}, ("opacity", 1.0, 0.25))]
    for change, (field, before, after) in cases:
        r = await op(api, wid, a, {"type": "update_panel_layer", "id": red, **change})
        assert r.status_code == 200, r.text
        got = await layer(api, wid, a, red)
        assert got[field] == after and field in got["human_hand_fields"]
        await undo(api, wid, a, r.json()["event_id"])
        got = await layer(api, wid, a, red)
        assert got[field] == before, field
        # 取り消すと人の手の印も元に戻る（足した層なので、作ったときの印は残る）
        assert field in got["human_hand_fields"]

    # 固定（動かさない）：掛けると人も変えられない。取り消すと外れ、また変えられる
    r = await op(api, wid, a, {"type": "set_fixed", "target_kind": "panel_layer", "id": red, "fixed": True})
    assert r.status_code == 200, r.text
    assert (await layer(api, wid, a, red))["fixed"] is True
    refused = await op(api, wid, a, {"type": "update_panel_layer", "id": red, "visible": False})
    assert refused.status_code == 409, refused.text
    await undo(api, wid, a, r.json()["event_id"])
    assert (await layer(api, wid, a, red))["fixed"] is False
    assert (await op(api, wid, a, {"type": "update_panel_layer", "id": red, "visible": False})).status_code == 200


async def test_トーンの層の順_見せるか_不透明度_固定をそれぞれ変えて取り消せる(api, authz, image_dir):  # noqa: F811
    a = user()
    wid, p1, panel, _ = await layered_page(api, a)
    tones = []
    for order in (1, 2):
        tid = uuid.uuid4().hex
        r = await op(api, wid, a, {"type": "add_page_item", "id": tid, "page_id": p1, "panel_id": panel,
                                   "item_kind": "tone", "stack_order": order, "box_mm": [0, 0, 150, 110],
                                   "spec": {"kind": "dots", "target": {"kind": "panel", "panel_id": panel},
                                            "color": "#000000", "density": 0.2, "lines_per_inch": 60,
                                            "angle_deg": 45}})
        assert r.status_code == 200, r.text
        tones.append(tid)
    t0, t1 = tones
    # 順を入れ替える（画面の「上へ」と同じ2つの操作）。取り消しは1つずつ
    r1 = await op(api, wid, a, {"type": "update_page_item", "id": t0, "stack_order": 2})
    r2 = await op(api, wid, a, {"type": "update_page_item", "id": t1, "stack_order": 1})
    assert r1.status_code == r2.status_code == 200
    assert [(await item(api, wid, a, t))["stack_order"] for t in tones] == [2, 1]
    await undo(api, wid, a, r2.json()["event_id"])
    await undo(api, wid, a, r1.json()["event_id"])
    assert [(await item(api, wid, a, t))["stack_order"] for t in tones] == [1, 2]
    for change, field, before in (({"visible": False}, "visible", True), ({"opacity": 0.4}, "opacity", 1.0)):
        r = await op(api, wid, a, {"type": "update_page_item", "id": t0, **change})
        assert r.status_code == 200, r.text
        assert (await item(api, wid, a, t0))[field] == change[field]
        await undo(api, wid, a, r.json()["event_id"])
        assert (await item(api, wid, a, t0))[field] == before
    r = await op(api, wid, a, {"type": "set_fixed", "target_kind": "page_item", "id": t0, "fixed": True})
    assert r.status_code == 200, r.text
    assert (await op(api, wid, a, {"type": "update_page_item", "id": t0, "opacity": 0.5})).status_code == 409
    await undo(api, wid, a, r.json()["event_id"])
    assert (await op(api, wid, a, {"type": "update_page_item", "id": t0, "opacity": 0.5})).status_code == 200


async def test_人が変えた層の項目はAIが変えず判断待ちに置く(api, authz, image_dir):  # noqa: F811
    a = user()
    wid, _, panel, ly = await layered_page(api, a)
    await allow_ai(api, wid, a, "drawing")
    blue = ly["blue"]
    # 人が見せる・不透明度を変えた。AI の変更は書かずに判断待ちにする
    assert (await op(api, wid, a, {"type": "update_panel_layer", "id": blue, "visible": False,
                                   "opacity": 0.5})).status_code == 200
    ev = await ai_op(authz, wid, a, {"type": "update_panel_layer", "id": blue, "visible": True, "opacity": 0.9})
    assert sorted(x["field"] for x in ev.held_changes) == ["opacity", "visible"]
    got = await layer(api, wid, a, blue)
    assert (got["visible"], got["opacity"]) == (False, 0.5)
    held = (await api.get(f"/works/{wid}/held-changes", headers=h(a))).json()
    assert {x["field"] for x in held if x["target_id"] == blue} == {"opacity", "visible"}
    # 人が印を外した項目は AI が変えられる
    assert (await op(api, wid, a, {"type": "update_panel_layer", "id": blue,
                                   "human_hand_fields": ["image_id", "placement", "role", "stack_order"]})
            ).status_code == 200
    ev = await ai_op(authz, wid, a, {"type": "update_panel_layer", "id": blue, "opacity": 0.9})
    assert not ev.held_changes
    assert (await layer(api, wid, a, blue))["opacity"] == 0.9
    # 人の手の層は AI が作れない・変えられない
    with pytest.raises(Exception, match="人の手の層"):
        await ai_op(authz, wid, a, {"type": "add_panel_layer", "panel_id": panel, "role": "human_hand",
                                    "stack_order": 9})
    hand = uuid.uuid4().hex
    assert (await op(api, wid, a, {"type": "add_panel_layer", "id": hand, "panel_id": panel, "role": "human_hand",
                                   "stack_order": 9})).status_code == 200
    with pytest.raises(Exception, match="人の手の層"):
        await ai_op(authz, wid, a, {"type": "update_panel_layer", "id": hand, "visible": False})
    # 固定の層は AI も変えられない（判断待ちにもしない）
    assert (await op(api, wid, a, {"type": "set_fixed", "target_kind": "panel_layer", "id": blue,
                                   "fixed": True})).status_code == 200
    with pytest.raises(Exception, match="動かさない"):
        await ai_op(authz, wid, a, {"type": "update_panel_layer", "id": blue, "opacity": 0.1})
    # AI は人の手の印を外せない
    with pytest.raises(HumanHandProtected):
        await ai_op(authz, wid, a, {"type": "update_panel_layer", "id": ly["red"], "human_hand_fields": []})


def _center(img: Image.Image) -> tuple[int, int, int]:
    """層を置いた所（BOX）の真ん中の画素。基本枠の mm → 塗り足し込みの画素。"""
    k = DPI / 25.4
    ox = (PAGE_SPEC["trim_width_mm"] - PAGE_SPEC["frame_width_mm"]) / 2 + PAGE_SPEC["bleed_mm"]
    oy = (PAGE_SPEC["trim_height_mm"] - PAGE_SPEC["frame_height_mm"]) / 2 + PAGE_SPEC["bleed_mm"]
    x, y = (BOX[0] + BOX[2]) / 2 + ox, (BOX[1] + BOX[3]) / 2 + oy
    return tuple(int(v) for v in np.asarray(img.convert("RGB"))[round(y * k), round(x * k)])


def _near(px, rgba) -> bool:
    return all(abs(a - b) <= 8 for a, b in zip(px, rgba[:3], strict=False))


@pytest.mark.full
@needs_font
async def test_書き出しは層の見せるかと順に従う(api, authz, workers, export_env):  # noqa: F811
    a = user()
    wid, p1, _, ly = await layered_page(api, a)

    async def center():
        run = await _export(api, wid, a, {"format": "png", "page_ids": [p1]})
        assert run["status"] == "done", run["detail"]
        return _center(Image.open(io.BytesIO(await _file(api, wid, a, run, run["outputs"][0]["file"]))))

    assert _near(await center(), BLUE), "上の層（青）が見える"
    # 順を入れ替える → 赤が上
    assert (await op(api, wid, a, {"type": "update_panel_layer", "id": ly["red"], "stack_order": 3})).status_code == 200
    assert _near(await center(), RED), "順を変えると赤が上になる"
    # 赤を隠す → 青が見える
    r = await op(api, wid, a, {"type": "update_panel_layer", "id": ly["red"], "visible": False})
    assert r.status_code == 200
    assert _near(await center(), BLUE), "上の層を隠すと下の層が見える"
    # 取り消すとまた赤
    await undo(api, wid, a, r.json()["event_id"])
    assert _near(await center(), RED), "隠したのを取り消すと上の層がまた見える"
