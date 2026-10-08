"""コマ割りの計算の試験。根拠は試作 p12（段と比からの座標）と p34（左から読む割りの反転）の数字。"""
import math

import pytest

from name_draft_samples import P12_ANSWERS, SPEC, draft_of, p12_page, simple_pages
from v3server.name_checks import frame_shape_checks as fsc
from v3server.name_structure.reading_direction import PageSpec
from v3server.panel_layout.layout_rough_image import RoughStyle, draw_page_rough, draw_polygons
from v3server.panel_layout.panel_geometry import (box_iou, ellipse_box_coverage, polygon_area, polygon_bbox, polygon_centroid,
                                                  polygon_distance, polygon_overlap_area, rect_polygon, shrink_polygon)
from v3server.panel_layout.reading_direction_mirror import (before_turn_page_indices, facing_page_pairs, mirror_polygon,
                                                           page_sides)
from v3server.panel_layout.tier_ratio_layout import LayoutInputError, layout_draft, page_frames, tier_boxes

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
        assert polygon_bbox(mirror_polygon(rect_polygon(rtl[n]), SPEC)) == pytest.approx(ltr[n])


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
