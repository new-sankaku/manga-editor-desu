"""ネームの検査の試験。根拠は試作 p12（読む順の崩れ・「大」の広さ）・p27（数え方）・p34（めくり）・p40（単調さ）・p47（顔の隠れ）。"""
import math

import pytest
from name_draft_samples import SPEC, draft_of, p12_page, panel, simple_pages

from v3server.name_checks import frame_shape_checks as fsc
from v3server.name_checks import page_rhythm_checks as prc
from v3server.name_checks import shot_sequence_checks as ssc
from v3server.name_checks.balloon_face_overlap import check_balloon_face_overlap
from v3server.name_checks.balloon_text_checks import (
    check_balloon_chars,
    check_balloon_crossing,
    check_balloon_order,
    check_page_chars,
)
from v3server.name_checks.name_check_runner import ALL_THRESHOLD_KEYS, run_name_checks
from v3server.name_checks.page_monotony_metrics import run_monotony_checks
from v3server.name_structure.name_draft_schema import Balloon, FigureInPanel, NamePage
from v3server.panel_layout.tier_ratio_layout import layout_draft


def laid(answer_id: str, **kw):
    return layout_draft(draft_of([p12_page(answer_id)], **kw))


# ---- 読む順（p12） ----

@pytest.mark.parametrize("answer_id, bad_panel", [("s1_talk_B_4", 4), ("s3_action_B_0", 7)])
def test_p12_order_breaks_found_in_rows(answer_id, bad_panel):
    """p12 の「段と比」の崩れ（台本の順の入れ替え・段の中を左から）は、段の番号の並びで見つかる。"""
    r = fsc.check_rows_order(draft_of([p12_page(answer_id)]), {})
    assert r.status == "不合格"
    assert r.findings[0].panel == bad_panel


def test_p12_order_breaks_found_in_frames():
    """p12 の検査では s1_talk_B_4 の崩れは1つ。"""
    r = fsc.check_frame_reading_order(laid("s1_talk_B_4"), {})
    assert r.status == "不合格" and len(r.findings) == 1 and r.findings[0].panel == 4
    assert fsc.check_frame_reading_order(laid("s1_talk_B_1"), {}).status == "合格"


def test_p12_big_is_largest():
    """p12：s1_talk_B_0 は「大」がいちばん広くない、B_1 は広い。"""
    assert fsc.check_big_is_largest(laid("s1_talk_B_0"), {}).status == "不合格"
    assert fsc.check_big_is_largest(laid("s1_talk_B_1"), {}).status == "合格"


def test_frame_checks_without_frames_say_no_data():
    d = draft_of([p12_page("s1_talk_B_1")])
    assert fsc.check_overlap(d, {}).status == "データなし"


def test_overlap_gap_tiny_and_empty():
    d = laid("s1_talk_B_1")
    pg = d.pages[0]
    # コマ3を右へずらしてコマ2に重ねる
    moved = [(x + 5, y) for x, y in pg.panels[2].frame.polygon_mm]
    p3 = pg.panels[2].model_copy(update={"frame": pg.panels[2].frame.model_copy(update={"polygon_mm": moved})})
    bad = d.model_copy(update={"pages": [pg.model_copy(update={"panels": pg.panels[:2] + [p3] + pg.panels[3:]})]})
    r = fsc.check_overlap(bad, {})
    assert r.status == "不合格" and r.findings[0].panel == 2
    assert fsc.check_frame_bounds(bad, {}).status == "合格"
    # 隙間の閾値が無ければ値だけ、あれば合否
    assert fsc.check_panel_gap(d, {}).status == "閾値未設定"
    assert fsc.check_panel_gap(d, {"panel_gap_min_mm": 3}).status == "不合格"
    assert fsc.check_tiny_panel(d, {"panel_short_side_min_mm": 15}).status == "合格"
    assert fsc.check_tiny_panel(d, {"panel_short_side_min_mm": 40}).findings[0].panel in (1, 4)
    # コマ4を抜くと、その面積が空く（隙間の分は数えない）
    holed = d.model_copy(update={"pages": [pg.model_copy(update={"panels": [p for p in pg.panels if p.n != 4]})]})
    empty = fsc.page_empty_area_mm2(holed.pages[0], holed)
    assert 150 * 37.27 * 0.8 < empty < 150 * 37.27
    assert fsc.check_empty_space(holed, {"empty_area_max_mm2": 100}).status == "不合格"


def test_row_cut_offset_and_facing_lines():
    """s3_action_B_0 は2コマの段が3つ続き、縦線が揃う（ずれ0）。"""
    d = laid("s3_action_B_0")
    r = fsc.check_row_cut_offset(d, {"row_cut_offset_min_mm": 5})
    assert r.value == 0 and r.status == "不合格"
    pages = [p12_page("s1_talk_B_1", 1), p12_page("s1_talk_B_1", 2), p12_page("s1_talk_B_1", 3)]
    # 2ページ目と3ページ目のコマの番号を通しにする
    renum = []
    off = 0
    for pg in pages:
        renum.append(pg.model_copy(update={"rows": [[n + off for n in row] for row in pg.rows],
                                           "panels": [p.model_copy(update={"n": p.n + off}) for p in pg.panels]}))
        off += 6
    dd = layout_draft(draft_of(renum))
    r = fsc.check_facing_row_line_offset(dd, {"facing_row_line_offset_min_mm": 1})
    assert r.status == "不合格" and r.findings[0].page == 2


def test_gutter_side_and_inside_frame():
    face_in_gutter = FigureInPanel(name="A", face="大", facing="左", face_box_mm=(140, 10, 155, 25))
    b_out = Balloon(speaker="A", kind="台詞", text="あ", box_mm=(100, -5, 120, 10))
    pages = simple_pages(2)
    pages[0].panels[0] = pages[0].panels[0].model_copy(update={"people": [face_in_gutter], "balloons": [b_out]})
    d = layout_draft(draft_of(pages))
    r = fsc.check_gutter_side_contents(d, {})
    # 1ページ目は左のページなので、ノドは右（x=150）。顔が x=155 まで出ている
    assert r.status == "不合格" and r.findings[0].note.startswith("顔")
    assert fsc.check_balloon_inside_frame(d, {}).status == "不合格"


# ---- 閾値と報告の形 ----

def test_runner_without_thresholds_gives_no_pass_fail_for_threshold_checks():
    d = laid("s1_talk_B_1")
    rep = run_name_checks(d, {})
    for r in rep.results:
        if r.threshold_key is not None:
            assert r.status == "閾値未設定", r.check_id
    assert rep.by_id("panels_per_page_max").value == 6
    assert rep.by_id("frame_reading_order").status == "合格"


def test_runner_rejects_unknown_key():
    with pytest.raises(KeyError):
        run_name_checks(laid("s1_talk_B_1"), {"panel_count_max": 8})


def test_report_lines_pass_is_one_line_fail_is_detailed():
    d = laid("s1_talk_B_1")
    ok = prc.check_panels_per_page(d, {"panels_per_page_max": 8})[0]
    assert ok.status == "合格" and len(ok.report_lines()) == 1
    ng = prc.check_panels_per_page(d, {"panels_per_page_max": 5})[0]
    lines = ng.report_lines()
    assert ng.status == "不合格" and len(lines) == 2 and "1ページ" in lines[1] and "6" in lines[1]
    assert set(ALL_THRESHOLD_KEYS) >= {"panels_per_page_max", "face_covered_ratio_max"}


# ---- めくり（p34・p27） ----

def _hooked(pages: list[NamePage], hook_ns: set[int]) -> list[NamePage]:
    return [pg.model_copy(update={"panels": [p.model_copy(update={"hook": p.n in hook_ns}) for p in pg.panels]}) for pg in pages]


def test_hooks_and_first_page():
    pages = _hooked(simple_pages(4), {2, 6})  # 1ページ目と3ページ目の最後
    d = draft_of(pages)
    assert prc.check_first_page_side(d, {}).status == "合格"
    assert prc.check_hook_at_turn(d, {}).status == "合格"
    assert prc.check_hook_position(d, {}).status == "合格"
    missing = draft_of(_hooked(simple_pages(4), {2}))
    assert prc.check_hook_at_turn(missing, {}).findings[0].panel == 6
    misplaced = draft_of(_hooked(simple_pages(4), {2, 6, 3}))
    assert prc.check_hook_position(misplaced, {}).findings[0].panel == 3
    # 右から読む本で1ページ目が右は外れ。左から読む本では1ページ目が右で合う
    assert prc.check_first_page_side(draft_of(pages, first_page_is_left=False), {}).status == "不合格"
    assert prc.check_first_page_side(draft_of(pages, "left_to_right", first_page_is_left=False), {}).status == "合格"


def test_turn_panel_size():
    pages = simple_pages(2)
    pages[0].panels[1] = pages[0].panels[1].model_copy(update={"size": "大", "hook": True})
    pages[1].panels[0] = pages[1].panels[0].model_copy(update={"size": "中"})
    r = prc.check_turn_panel_size(draft_of(pages), {})
    assert r.status == "不合格" and r.findings[0].panel == 3
    pages[1].panels[0] = pages[1].panels[0].model_copy(update={"size": "大"})
    assert prc.check_turn_panel_size(draft_of(pages), {}).status == "合格"


# ---- 数える検査（p27） ----

def test_rhythm_counts():
    pages = simple_pages(3)
    d = draft_of(pages)
    r = prc.check_same_row_pattern_next_page(d, {"same_row_pattern_next_page_max": 1})
    assert r.value == 2 and r.status == "不合格" and [f.page for f in r.findings] == [2, 3]
    assert prc.check_pages_without_big(d, {}).value == 3
    assert prc.check_same_size_run(d, {"same_size_run_max": 4}).findings[0].value == 6


def test_shot_sequence():
    ps = [panel(1, shot="顔"), panel(2, shot="顔"), panel(3, shot="胸から上", angle="見上げ"),
          panel(4, shot="引き", scene=2, background="描き込む"), panel(5, shot="顔", scene=3)]
    d = draft_of([NamePage(page=1, spread=False, rows=[[1, 2, 3, 4, 5]], panels=ps)])
    assert ssc.check_same_shot_angle_next(d, {}).value == 1
    assert ssc.check_close_shot_run(d, {"close_shot_run_max": 2}).findings[0].value == 3
    r = ssc.check_place_shown(d, {})
    assert r.status == "不合格" and [f.panel for f in r.findings] == [1, 5]
    assert ssc.check_unusual_angle_ratio(d, {}).value == 0.2
    assert ssc.check_full_body_interval(d, {}).value == 0


def test_conversation_sides_swap():
    def two(n, a_x, b_x):
        return panel(n, people=[FigureInPanel(name="A", face="中", facing="左", box_mm=(a_x, 0, a_x + 10, 50)),
                                FigureInPanel(name="B", face="中", facing="右", box_mm=(b_x, 0, b_x + 10, 50))])
    ok = draft_of([NamePage(page=1, spread=False, rows=[[1, 2]], panels=[two(1, 10, 50), two(2, 0, 60)])])
    assert ssc.check_conversation_sides(ok, {}).status == "合格"
    ng = draft_of([NamePage(page=1, spread=False, rows=[[1, 2]], panels=[two(1, 10, 50), two(2, 60, 0)])])
    assert ssc.check_conversation_sides(ng, {}).findings[0].panel == 2
    assert ssc.check_conversation_sides(draft_of(simple_pages(1)), {}).status == "データなし"


# ---- 吹き出し ----

def _with_balloons(boxes, direction="right_to_left"):
    bl = [Balloon(speaker="A", kind="台詞", text="こんにちは\n元気", box_mm=b) for b in boxes]
    return draft_of([NamePage(page=1, spread=False, rows=[[1]], panels=[panel(1, balloons=bl)])], direction,
                    first_page_is_left=direction == "right_to_left")


def test_balloon_text_counts():
    d = _with_balloons([None])
    assert check_balloon_chars(d, {}).value == 7  # 改行を数えない
    assert check_page_chars(d, {"page_chars_max": 5}).status == "不合格"


def test_balloon_order_and_crossing():
    right_first = [(100, 10, 120, 40), (60, 20, 80, 50)]
    assert check_balloon_order(_with_balloons(right_first), {}).status == "合格"
    assert check_balloon_order(_with_balloons(right_first[::-1]), {}).status == "不合格"
    # 左から読む作品では逆が正しい
    assert check_balloon_order(_with_balloons(right_first[::-1], "left_to_right"), {}).status == "合格"
    assert check_balloon_crossing(_with_balloons(right_first), {}).status == "合格"
    assert check_balloon_crossing(_with_balloons([(0, 0, 20, 20), (10, 0, 30, 20)]), {}).status == "不合格"
    assert check_balloon_order(_with_balloons([None]), {}).status == "データなし"


def test_balloon_face_overlap():
    """p47：重ねる前の顔の位置から、隠れは重なりの計算で分かる。楕円が顔の四角と同じなら π/4 を覆う。"""
    face = FigureInPanel(name="A", face="大", facing="正面", face_box_mm=(10, 10, 30, 30))
    bl = [Balloon(speaker="A", kind="台詞", text="あ", box_mm=(10, 10, 30, 30))]
    d = draft_of([NamePage(page=1, spread=False, rows=[[1]], panels=[panel(1, people=[face], balloons=bl)])])
    r = check_balloon_face_overlap(d, {})
    assert r.status == "閾値未設定" and r.value == pytest.approx(math.pi / 4, abs=1e-3)
    assert check_balloon_face_overlap(d, {"face_covered_ratio_max": 0.5}).findings[0].balloon == 0
    assert check_balloon_face_overlap(draft_of(simple_pages(1)), {}).status == "データなし"


# ---- 単調さ（p40） ----

def test_monotony_metrics():
    """同じ大きさのコマを格子に並べると、面積のばらつき0・形1種・上の辺は全部揃う。"""
    d = layout_draft(draft_of(simple_pages(3)))
    rs = {r.check_id: r for r in run_monotony_checks(d, {"aspect_wide_min": 1.3, "aspect_tall_max": 0.77,
                                                         "area_cv_median_min": 0.3, "single_shape_page_ratio_max": 0.5})}
    assert rs["area_cv_median"].value == 0 and rs["area_cv_median"].status == "不合格"
    assert rs["single_shape_page_ratio"].value == 1 and len(rs["single_shape_page_ratio"].findings) == 3
    assert rs["top_aligned_ratio_median"].value == 1
    assert rs["full_width_ratio_median"].value == 0
    no_aspect = {r.check_id: r for r in run_monotony_checks(d, {})}
    assert no_aspect["single_shape_page_ratio"].status == "閾値未設定"
    # p12 の s1_talk_B_1 は幅いっぱいのコマが6つ中2つ
    one = {r.check_id: r for r in run_monotony_checks(laid("s1_talk_B_1"), {})}
    assert one["full_width_ratio_median"].value == pytest.approx(2 / 6, abs=1e-3)
    assert SPEC.frame_width_mm == 150


# ---- 省略可の項目（無ければ今の振る舞い） ----

def test_intended_overlap_not_reported():
    d = laid("s1_talk_B_1")
    pg = d.pages[0]
    moved = [(x + 5, y) for x, y in pg.panels[2].frame.polygon_mm]
    p3 = pg.panels[2].model_copy(update={"frame": pg.panels[2].frame.model_copy(update={"polygon_mm": moved})})
    bad = d.model_copy(update={"pages": [pg.model_copy(update={"panels": pg.panels[:2] + [p3] + pg.panels[3:]})]})
    assert fsc.check_overlap(bad, {}).status == "不合格"
    p3b = p3.model_copy(update={"overlaps": [2]})
    ok = d.model_copy(update={"pages": [pg.model_copy(update={"panels": pg.panels[:2] + [p3b] + pg.panels[3:]})]})
    assert fsc.check_overlap(ok, {}).status == "合格"


def test_joined_balloons_not_crossing():
    boxes = [(0, 0, 20, 20), (10, 0, 30, 20)]
    bl = [Balloon(speaker="A", kind="台詞", text="あ", box_mm=boxes[0]),
          Balloon(speaker="A", kind="台詞", text="い", box_mm=boxes[1], joined_to_previous=True)]
    d = draft_of([NamePage(page=1, spread=False, rows=[[1]], panels=[panel(1, balloons=bl)])])
    assert check_balloon_crossing(d, {}).status == "合格"


def test_place_shown_by_location():
    """場所の名前があれば場所で区切る。場面の番号が変わっても同じ場所なら、場所を見せ直さなくてよい。"""
    ps = [panel(1, shot="引き", background="描き込む", scene=1, location="教室"),
          panel(2, shot="顔", scene=2, location="教室"),
          panel(3, shot="顔", scene=3, location="廊下")]
    d = draft_of([NamePage(page=1, spread=False, rows=[[1, 2, 3]], panels=ps)])
    r = ssc.check_place_shown(d, {})
    assert r.status == "不合格" and [f.panel for f in r.findings] == [3]
    mixed = [ps[0], ps[1].model_copy(update={"location": None}), ps[2]]
    d2 = draft_of([NamePage(page=1, spread=False, rows=[[1, 2, 3]], panels=mixed)])
    assert ssc.check_place_shown(d2, {}).status == "データなし"


def test_two_page_spread():
    """2ページ分の見開きは左右の2ページとして数える。右から読む本で、めくりの後の側（右）から始まれば合う。"""
    from v3server.panel_layout.reading_direction_mirror import before_turn_page_indices, page_sides
    pages = simple_pages(3)
    pages[1] = pages[1].model_copy(update={"spread": True, "spread_occupies_two_pages": True})
    d = draft_of(pages)
    # 1ページ目は左、見開きは右と左、3つ目は右
    assert page_sides(d) == ["左", "右", "右"]
    assert before_turn_page_indices(d) == [0, 1]
    assert prc.check_spread_position(d, {}).status == "合格"
    late = simple_pages(4)
    late[2] = late[2].model_copy(update={"spread": True, "spread_occupies_two_pages": True})
    assert prc.check_spread_position(draft_of(late), {}).status == "不合格"
    undecided = simple_pages(3)
    undecided[1] = undecided[1].model_copy(update={"spread": True})
    assert prc.check_spread_position(draft_of(undecided), {}).status == "データなし"
    # 見開きのノド（x = 150 + 16）をまたぐ吹き出しは指摘、またぐコマはよい
    bl = Balloon(speaker="A", kind="台詞", text="あ", box_mm=(160, 10, 175, 30))
    sp = NamePage(page=2, spread=True, spread_occupies_two_pages=True, rows=[[3]],
                  panels=[panel(3, balloons=[bl], frame={"polygon_mm": [(0, 0), (316, 0), (316, 220), (0, 220)], "bleeds": False})])
    d3 = draft_of([pages[0], sp])
    assert fsc.check_gutter_side_contents(d3, {}).findings[0].note.startswith("吹き出し")
    assert fsc.check_frame_bounds(d3.model_copy(update={"pages": [sp]}), {}).status == "合格"
