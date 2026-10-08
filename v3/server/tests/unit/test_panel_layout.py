"""コマ割りの計算の試験。根拠は試作 p12（段と比からの座標）と p34（左から読む割りの反転）の数字。"""
import math

import pytest
from name_draft_samples import P12_ANSWERS, SPEC, draft_of, p12_page, simple_pages

from v3server.name_checks import frame_shape_checks as fsc
from v3server.name_structure.reading_direction import PageSpec
from v3server.panel_layout.layout_rough_image import (
    RoughStyle,
    draw_page_rough,
    draw_polygons,
)
from v3server.panel_layout.panel_geometry import (
    box_iou,
    ellipse_box_coverage,
    polygon_area,
    polygon_bbox,
    polygon_centroid,
    polygon_distance,
    polygon_overlap_area,
    rect_polygon,
    shrink_polygon,
)
from v3server.panel_layout.reading_direction_mirror import (
    before_turn_page_indices,
    facing_page_pairs,
    mirror_polygon,
    page_sides,
)
from v3server.panel_layout.tier_ratio_layout import (
    LayoutInputError,
    layout_draft,
    page_frames,
    tier_boxes,
)

# p12 の s1_talk_B_1 の計算結果（x, y, w, h）。p12 `rows_to_panels` の出力を写した
P12_S1_B1 = {1: (0.0, 0.0, 150.0, 37.273), 2: (61.2, 42.273, 88.8, 55.909), 3: (0.0, 42.273, 59.2, 55.909),
             4: (0.0, 103.182, 150.0, 37.273), 5: (61.2, 145.455, 88.8, 74.545), 6: (0.0, 145.455, 59.2, 74.545)}


def test_tier_boxes_match_p12():
    boxes = tier_boxes(p12_page("s1_talk_B_1"), SPEC, "right_to_left")
    for n, (x, y, w, h) in P12_S1_B1.items():
        got = boxes[n]
        assert got == pytest.approx((x, y, x + w, y + h), abs=1e-3)


@pytest.mark.parametrize("answer_id", list(P12_ANSWERS))
def test_layout_stays_in_frame_and_fills_it(answer_id):
    """p12 の「段と比」は空いた場所0・はみ出し0・重なり0・隙間1mm未満0（48回すべて）。"""
    d = layout_draft(draft_of([p12_page(answer_id)]))
    for name in ("check_frame_bounds", "check_overlap", "check_gutter_ratio"):
        assert getattr(fsc, name)(d, {}).status == "合格", name
    assert fsc.check_panel_gap(d, {"panel_gap_min_mm": 1}).status == "合格"
    assert fsc.page_empty_area_mm2(d.pages[0], d) == 0
    # 隙間は規格どおり
    assert fsc.check_panel_gap(d, {}).value == pytest.approx(SPEC.gutter_x_mm)


def test_left_to_right_layout_is_mirror_of_right_to_left():
    page = p12_page("s1_talk_B_1")
    rtl, ltr = tier_boxes(page, SPEC, "right_to_left"), tier_boxes(page, SPEC, "left_to_right")
    for n in rtl:
        assert polygon_bbox(mirror_polygon(rect_polygon(rtl[n]), SPEC.frame_width_mm)) == pytest.approx(ltr[n])


@pytest.mark.parametrize("answer_id", list(P12_ANSWERS))
def test_mirrored_layout_checks_same_as_original(answer_id):
    """p34：反転した割りを「左から」で検査すると48/48で元と同じ結果。"""
    rtl = layout_draft(draft_of([p12_page(answer_id)], "right_to_left"))
    ltr = layout_draft(draft_of([p12_page(answer_id)], "left_to_right", first_page_is_left=False))
    for f in fsc.FRAME_SHAPE_CHECKS:
        a, b = f(rtl, {}), f(ltr, {})
        assert (a.status, a.value, [x.panel for x in a.findings]) == (b.status, b.value, [x.panel for x in b.findings]), f.__name__


@pytest.mark.parametrize("answer_id", ["s1_talk_B_0", "s1_talk_B_1"])
def test_wrong_direction_is_caught(answer_id):
    """p34：左から読む割りを誤って「右から」で検査すると48/48で読む順の崩れとして出た。"""
    ltr = layout_draft(draft_of([p12_page(answer_id)], "left_to_right", first_page_is_left=False))
    wrong = ltr.model_copy(update={"reading_direction": "right_to_left"})
    assert fsc.check_frame_reading_order(ltr, {}).status == "合格"
    assert fsc.check_frame_reading_order(wrong, {}).status == "不合格"


def test_bleed_not_toward_gutter():
    page = p12_page("s1_talk_B_1")
    page.panels[0] = page.panels[0].model_copy(update={"shape": "断ち切り"})  # コマ1は1段目の全幅
    ox, oy = SPEC.frame_origin_in_trim()
    left = polygon_bbox(page_frames(page, SPEC, "right_to_left", "左")[1].polygon_mm)
    right = polygon_bbox(page_frames(page, SPEC, "right_to_left", "右")[1].polygon_mm)
    # 左のページはノドが右：右の辺は基本枠に留まる
    assert left == pytest.approx((-ox - SPEC.bleed_mm, -oy - SPEC.bleed_mm, SPEC.frame_width_mm, 37.273), abs=1e-3)
    assert right == pytest.approx((0.0, -oy - SPEC.bleed_mm, SPEC.frame_width_mm + ox + SPEC.bleed_mm, 37.273), abs=1e-3)
    assert page_frames(page, SPEC, "right_to_left", "左")[1].bleeds
    # 2段目の右のコマ（コマ2）は、基本枠に接する辺がノドの辺だけなので、断ち切りの指定でも伸びない
    page.panels[1] = page.panels[1].model_copy(update={"shape": "断ち切り"})
    inner = page_frames(page, SPEC, "right_to_left", "左")[2]
    assert not inner.bleeds and polygon_bbox(inner.polygon_mm)[0] == pytest.approx(61.2)


def test_page_sides_and_turns():
    """p34：右から読む本は1ページ目が左、めくりの前は左のページ。左から読む本は逆。"""
    rtl = draft_of(simple_pages(4))
    assert page_sides(rtl) == ["左", "右", "左", "右"]
    assert before_turn_page_indices(rtl) == [0, 2]
    assert facing_page_pairs(rtl) == [(1, 2)]
    ltr = draft_of(simple_pages(4), "left_to_right", first_page_is_left=False)
    assert page_sides(ltr) == ["右", "左", "右", "左"]
    assert before_turn_page_indices(ltr) == [0, 2]


def test_layout_refuses_bad_input():
    page = p12_page("s1_talk_B_1")
    with pytest.raises(LayoutInputError):
        tier_boxes(page.model_copy(update={"row_height_ratios": None}), SPEC, "right_to_left")
    with pytest.raises(LayoutInputError):
        tier_boxes(page.model_copy(update={"cell_width_ratios": [[1.0]] * 4}), SPEC, "right_to_left")
    with pytest.raises(LayoutInputError):
        tier_boxes(page.model_copy(update={"spread": True}), SPEC, "right_to_left")
    wide_x = PageSpec(**{**SPEC.model_dump(), "gutter_x_mm": 5})
    with pytest.raises(LayoutInputError):
        tier_boxes(page, wide_x, "right_to_left")


def test_geometry():
    a = rect_polygon((0, 0, 10, 10))
    b = rect_polygon((5, 5, 15, 15))
    assert polygon_area(a) == 100
    assert polygon_overlap_area(a, b) == pytest.approx(25)
    assert polygon_centroid(a) == pytest.approx((5, 5))
    assert polygon_distance(a, rect_polygon((12, 0, 20, 10))) == pytest.approx(2)
    assert polygon_distance(a, b) == 0
    assert box_iou((0, 0, 10, 10), (5, 0, 15, 10)) == pytest.approx(50 / 150)
    tri = [(0, 0), (10, 0), (0, 10)]
    assert polygon_overlap_area(tri, a) == pytest.approx(50)
    # 楕円が四角いっぱいなら π/4 を覆う
    assert ellipse_box_coverage((0, 0, 10, 10), (0, 0, 10, 10)) == pytest.approx(math.pi / 4, abs=1e-4)
    assert ellipse_box_coverage((20, 0, 30, 10), (0, 0, 10, 10)) == 0
    s = shrink_polygon(a, math.sqrt(2))
    assert polygon_bbox(s) == pytest.approx((1, 1, 9, 9))


def test_rough_image():
    d = layout_draft(draft_of([p12_page("s1_talk_B_1")]))
    style = RoughStyle(px_per_mm=2, line_px=2, show_numbers=True, font_px=12, font_path=None, shrink_mm=None,
                       show_figures=True, show_balloons=True, show_balloon_text=False)
    img = draw_page_rough(d.pages[0], SPEC, style)
    assert img.size == (round((182 + 6) * 2), round((257 + 6) * 2))
    ox, oy = SPEC.frame_origin_in_trim()
    to_px = lambda x, y: (round((x + ox + 3) * 2), round((y + oy + 3) * 2))
    # コマ1の上の辺は黒、コマ4の中は白
    assert img.getpixel(to_px(75, 0)) == (0, 0, 0)
    assert img.getpixel(to_px(20, 110)) == (255, 255, 255)
    # 斜めのコマは縮めて描ける（p45）
    tri = {1: [(0, 0), (150, 0), (0, 100)], 2: [(150, 0), (150, 100), (0, 100)]}
    plain = RoughStyle(px_per_mm=2, line_px=2, show_numbers=False, font_px=12, font_path=None, shrink_mm=2,
                       show_figures=False, show_balloons=False, show_balloon_text=False)
    assert draw_polygons(tri, SPEC, plain).size == img.size


# ---- 制約で解く割り（kiwisolver。試作 p50）。人が決めた枠を固定し、残りが比を保って追従する ----

from v3server.name_structure.name_draft_schema import PanelFrame  # noqa: E402
from v3server.panel_layout.constrained_tier_layout import (  # noqa: E402
    LayoutConflictError,
    constrained_layout_draft,
    constrained_page_frames,
)


def _bboxes(frames):
    return {n: polygon_bbox(f.polygon_mm) for n, f in frames.items()}


def _pin(box):
    return PanelFrame(polygon_mm=rect_polygon(box), bleeds=False)


def test_constrained_without_pins_equals_tier_layout():
    page = p12_page("s1_talk_B_1")
    want = _bboxes(page_frames(page, SPEC, "right_to_left", "左"))
    res = constrained_page_frames(page, SPEC, "right_to_left", "左", {}, 20)
    assert res.broken == []
    for n, b in _bboxes(res.frames).items():
        assert b == pytest.approx(want[n], abs=1e-6)


def test_human_pins_one_panel_and_others_follow():
    """人がコマ2の左の辺を40mmへ動かす。同じ段のコマ3が縮み、ほかの段は動かない。"""
    page = p12_page("s1_talk_B_1")
    base = tier_boxes(page, SPEC, "right_to_left")
    x0, y0, x1, y1 = base[2]
    res = constrained_page_frames(page, SPEC, "right_to_left", "左", {2: _pin((40.0, y0, x1, y1))}, 20)
    got = _bboxes(res.frames)
    assert res.broken == []
    assert got[2] == pytest.approx((40.0, y0, x1, y1))
    assert got[3] == pytest.approx((0.0, y0, 40.0 - SPEC.gutter_x_mm, y1))
    for n in (1, 4, 5, 6):
        assert got[n] == pytest.approx(base[n], abs=1e-6)


def test_human_pins_row_height_and_other_rows_keep_ratio():
    """AIの段と比と、人の固定が混ざる：人がコマ5（最後の段）の上の辺を動かすと、残りの3段は比 2:3:2 を保つ。"""
    page = p12_page("s1_talk_B_1")
    base = tier_boxes(page, SPEC, "right_to_left")
    x0, _, x1, y1 = base[5]
    res = constrained_page_frames(page, SPEC, "right_to_left", "左", {5: _pin((x0, 120.0, x1, y1))}, 20)
    got = _bboxes(res.frames)
    assert res.broken == []
    h = [got[n][3] - got[n][1] for n in (1, 2, 4)]
    assert h[1] / h[0] == pytest.approx(1.5) and h[2] / h[0] == pytest.approx(1.0)
    assert got[6][1] == pytest.approx(120.0)  # 同じ段のコマ6も追従する


def test_pin_that_loses_is_reported():
    """p50：強い固定が必須（最小の大きさ）に負けると、例外にならず静かに崩れる。崩れたコマを必ず返す。"""
    page = p12_page("s1_talk_B_1")
    _, y0, x1, y1 = tier_boxes(page, SPEC, "right_to_left")[2]
    res = constrained_page_frames(page, SPEC, "right_to_left", "左", {2: _pin((10.0, y0, x1, y1))}, 20)
    assert [(b.panel, b.kind) for b in res.broken] == [(2, "固定した枠")]
    got = _bboxes(res.frames)
    # 人の枠は出力でも動かさない。隣のコマ3は最小の20mmで止まる
    assert got[2] == pytest.approx((10.0, y0, x1, y1))
    assert got[3][2] - got[3][0] == pytest.approx(20.0)


def test_two_pins_in_one_row_one_loses():
    """p50：強い固定を2つ（100+100）置くと、両立せず片方が崩れる。"""
    page = p12_page("s1_talk_B_1")
    base = tier_boxes(page, SPEC, "right_to_left")
    _, y0, _, y1 = base[5]
    pins = {5: _pin((50.0, y0, 150.0, y1)), 6: _pin((0.0, y0, 100.0, y1))}
    res = constrained_page_frames(page, SPEC, "right_to_left", "左", pins, 20)
    assert len(res.broken) == 1 and res.broken[0].kind == "固定した枠"


def test_required_conflict_raises():
    """p50：必須どうしが両立しなければ例外（UnsatisfiableConstraint）。4段は最小60mmに収まらない。"""
    with pytest.raises(LayoutConflictError):
        constrained_page_frames(p12_page("s1_talk_B_1"), SPEC, "right_to_left", "左", {}, 60)


def test_ratio_that_loses_to_minimum_is_reported():
    """p50：中の比 1:0.01 は最小の大きさに負けて崩れる。"""
    page = p12_page("s1_talk_B_1").model_copy(update={"row_height_ratios": [2.0, 3.0, 0.01, 4.0]})
    res = constrained_page_frames(page, SPEC, "right_to_left", "左", {}, 20)
    assert {b.kind for b in res.broken} == {"高さの比"}
    assert 4 in {b.panel for b in res.broken}


def test_all_panels_pinned_moves_nothing():
    """人が全部を決めた割りは、比が無くても何も動かさない（固定した枠をそのまま返す）。"""
    page = p12_page("s1_talk_B_1").model_copy(update={"row_height_ratios": None, "cell_width_ratios": None})
    pins = {n: PanelFrame(polygon_mm=[(x + 0.3, y), (x + 9, y), (x, y + 9)], bleeds=False)
            for n, (x, y) in zip(range(1, 7), [(0, 0), (20, 0), (40, 0), (0, 30), (20, 30), (40, 30)], strict=False)}
    d, broken = constrained_layout_draft(draft_of([page]), pins, 20)
    assert broken == []
    assert {p.n: p.frame for p in d.pages[0].panels} == pins


def test_slanted_cut_keeps_perpendicular_gutter():
    """p50：傾きを定数にすれば斜めの区切りは線形制約で書ける。垂直に測った隙間は規格どおり。"""
    page = p12_page("s1_talk_B_1").model_copy(update={"cut_slants": [[], [0.2], [], [0.0]]})
    res = constrained_page_frames(page, SPEC, "right_to_left", "左", {}, 20)
    assert res.broken == []
    p2, p3 = res.frames[2].polygon_mm, res.frames[3].polygon_mm
    assert polygon_distance(p2, p3) == pytest.approx(SPEC.gutter_x_mm, abs=1e-6)
    # 高さの真ん中で測った幅の比は 3:2
    mid = lambda poly: (polygon_area(poly) / (poly[3][1] - poly[0][1]))  # noqa: E731
    assert mid(p2) / mid(p3) == pytest.approx(1.5)
    with pytest.raises(LayoutInputError):
        tier_boxes(page, SPEC, "right_to_left")


def test_constrained_left_to_right_is_mirror():
    page = p12_page("s1_talk_B_1")
    rtl = _bboxes(constrained_page_frames(page, SPEC, "right_to_left", "左", {}, 20).frames)
    ltr = constrained_page_frames(page, SPEC, "left_to_right", "左", {}, 20).frames
    for n, f in ltr.items():
        assert polygon_bbox(mirror_polygon(f.polygon_mm, SPEC.frame_width_mm)) == pytest.approx(rtl[n], abs=1e-6)


def test_constrained_bleed_not_toward_gutter():
    page = p12_page("s1_talk_B_1")
    page.panels[0] = page.panels[0].model_copy(update={"shape": "断ち切り"})
    a = constrained_page_frames(page, SPEC, "right_to_left", "左", {}, 20).frames[1]
    b = page_frames(page, SPEC, "right_to_left", "左")[1]
    assert a.bleeds and polygon_bbox(a.polygon_mm) == pytest.approx(polygon_bbox(b.polygon_mm), abs=1e-6)
