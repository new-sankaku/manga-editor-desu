"""人・AI・取り込みのどれが作っても同じ流れに乗るか（データベースの要らない部品）。"""

import io

import pytest
from name_draft_samples import SPEC, draft_of, simple_pages
from PIL import Image
from pydantic import ValidationError

from v3server.canonical_tables.work_tree_tables import Panel, Work
from v3server.comfy_graphs.protected_region_mask import protected_mask_png
from v3server.llm_questions.answer_json_reader import BrokenAnswerError
from v3server.llm_questions.name_draft_question import parse_name_draft_answer
from v3server.name_checks.name_check_runner import CHECKS, run_name_checks
from v3server.name_import.manga_import_reader import MangaImportError, read_manga_import
from v3server.name_structure.image_placement import ImagePlacement
from v3server.name_structure.name_draft_schema import (
    NameDraft,
    NamePage,
    NamePanel,
    PanelFrame,
)
from v3server.operations.ai_involvement import (
    ABOUT_TASK,
    DESIGN_DEFAULT_MODE,
    HUMAN_EDITABLE_FIELDS,
    TASKS,
    ai_may,
    mode_of,
    require_ai_may_change_fields,
)
from v3server.operations.human_hand_guard import (
    drop_unchanged,
    split_held_changes,
)
from v3server.operations.text_and_layer_operations import TextItemValues
from v3server.panel_layout.tier_ratio_layout import LayoutInputError, layout_draft
from v3server.request_actor import Actor
from v3server.usage_terms_schema import UsageTerms
from v3server.v3_error_types import AiInvolvementRefused

AI = Actor(kind="ai", id="ai", on_behalf_of="u")
HUMAN = Actor(kind="human", id="u")


# ---------------------------------------------------------------- 検査は誰が作ったかを見ず、未定の項目だけで分ける


def test_検査の一覧に書いたidと_検査が返すidが合う():
    d = layout_draft(draft_of(simple_pages(2)))
    for entry in CHECKS:
        out = entry.fn(d, {})
        got = [r.check_id for r in (out if isinstance(out, list) else [out])]
        assert got == [i for i, _ in entry.ids], entry.fn.__name__


def test_一覧の要る項目は_未定にできる項目の名前だけ():
    names = {"rows", "balloons.kind", "balloons.speaker"} | set(NamePanel.model_fields) - {"n", "frame", "location",
                                                                                          "overlaps"}
    for entry in CHECKS:
        assert entry.needs <= names, entry.fn.__name__


def _frames_only_draft() -> NameDraft:
    """人がコマ枠の道具で枠だけ描いたページ（段の割りも中身も未定。斜めの枠を含む）。"""
    panels = [
        NamePanel(n=1, frame=PanelFrame(polygon_mm=[(0, 0), (150, 0), (150, 100), (0, 120)], bleeds=False)),
        NamePanel(n=2, frame=PanelFrame(polygon_mm=[(0, 125), (150, 105), (150, 220), (0, 220)], bleeds=False)),
    ]
    return draft_of([NamePage(page=1, spread=False, panels=panels)])


def test_枠だけのネームでも検査が回り_枠の検査は判定し_中身の検査はデータなし():
    d = _frames_only_draft()
    assert set(d.undecided_fields()) >= {"rows", "size", "shot", "balloons"}
    rep = run_name_checks(d, {"panel_gap_min_mm": 1.0})
    assert rep.by_id("panel_gap").status in ("合格", "不合格")
    assert rep.by_id("frame_bounds").status in ("合格", "不合格")
    assert rep.by_id("frame_reading_order").status in ("合格", "不合格")
    shot = rep.by_id("same_shot_angle_next")
    assert shot.status == "データなし" and "shot" in shot.value and "1ページ コマ1" in shot.value
    assert rep.by_id("rows_order").status == "データなし"
    # 全部の検査が1回ずつ結果を出す（未定でも抜けない）
    assert len(rep.results) == sum(len(e.ids) for e in CHECKS)


def test_全部決まったネームは今までどおり全部の検査が回る():
    d = layout_draft(draft_of(simple_pages(2)))
    assert d.undecided_fields() == {}
    rep = run_name_checks(d, {})
    assert not any(r.status == "データなし" and "未定" in str(r.value) for r in rep.results)


def test_段の割りが未定なら読む順はコマの番号の順で_割りの計算はしない():
    d = _frames_only_draft()
    with pytest.raises(LayoutInputError, match="rows"):
        layout_draft(d)


def test_AIの答えは未定の欄を許さない():
    answer = '{"pages": [{"page": 1, "spread": false, "rows": [[1]], "panels": [{"n": 1, "size": "大"}]}]}'
    with pytest.raises(BrokenAnswerError, match="欠けた欄"):
        parse_name_draft_answer(answer, "right_to_left", SPEC, True)


# ---------------------------------------------------------------- 取り込み（MangaImport）


def _doc(**panel_kw):
    panel = {"id": "p1", "reading_order": 1, "shape": "normal", "is_bleed": False,
             "points": [[0.0, 0.0], [1.0, 0.0], [1.0, 0.5], [0.0, 0.5]]} | panel_kw
    return {"format": "manga-editor-import", "version": 1, "pages": [{
        "index": 0, "source_file": "001.jpg", "width": 1820, "height": 2570,
        "panels": [panel, {"id": "p2", "reading_order": 2, "shape": "inferred", "is_bleed": False,
                           "points": [[0.1, 0.6], [0.9, 0.55], [0.9, 0.9], [0.1, 0.9]]}],
        "balloons": [
            {"id": "b1", "panel_id": "p1", "reading_order": 1, "type": "shout",
             "bbox": {"x": 0.5, "y": 0.1, "w": 0.1, "h": 0.1}, "text": "おい", "speaker": None, "excluded": False},
            {"id": "b2", "panel_id": "p1", "reading_order": 2, "type": "whisper",
             "bbox": {"x": 0.2, "y": 0.1, "w": 0.1, "h": 0.1}, "text": "…", "excluded": False},
            {"id": "b3", "panel_id": "p2", "reading_order": 3, "type": "normal",
             "bbox": {"x": 0.2, "y": 0.7, "w": 0.1, "h": 0.1}, "text": "ノイズ", "excluded": True,
             "exclusion_reason": "OCRの自信が低い"},
            {"id": "b4", "panel_id": None, "reading_order": 4, "type": "normal",
             "bbox": {"x": 0.2, "y": 0.7, "w": 0.1, "h": 0.1}, "text": "外", "excluded": False}]}]}


def test_取り込みの座標を基本枠のmmに直す():
    r = read_manga_import(_doc(), SPEC, "trim", first_page_number=3, first_panel_number=10)
    (page,) = r.pages
    assert page.page == 3 and page.rows is None and not page.spread
    p1, p2 = page.panels
    assert (p1.n, p2.n) == (10, 11)
    ox, oy = SPEC.frame_origin_in_trim()
    assert p1.frame.polygon_mm[0] == pytest.approx((-ox, -oy))
    assert p1.frame.polygon_mm[2] == pytest.approx((182 - ox, 128.5 - oy))
    # 塗り足しまで含む絵なら、その分ずらして縮める
    rb = read_manga_import(_doc(), SPEC, "trim_with_bleed", 1, 1)
    assert rb.pages[0].panels[0].frame.polygon_mm[0] == pytest.approx((-3 - ox, -3 - oy))


def test_取り込みは分かる所だけ読み_分からない所は未定にする():
    r = read_manga_import(_doc(), SPEC, "trim", 1, 1)
    p1, p2 = r.pages[0].panels
    assert p1.shape == "四角" and p2.shape is None  # inferred は未定
    assert [b.kind for b in p1.balloons] == ["叫び", None]  # whisper の種類は決めない
    assert p1.size is None and p1.shot is None and p1.people is None and p1.sfx is None
    assert [d["balloon_id"] for d in r.dropped] == ["b3", "b4"]
    slanted = read_manga_import(_doc(points=[[0, 0], [1, 0], [1, 0.4], [0, 0.5]]), SPEC, "trim", 1, 1)
    assert slanted.pages[0].panels[0].shape == "斜め"
    bleed = read_manga_import(_doc(is_bleed=True), SPEC, "trim", 1, 1)
    assert bleed.pages[0].panels[0].shape == "断ち切り" and bleed.pages[0].panels[0].frame.bleeds


def test_取り込みの形が崩れていれば止める():
    with pytest.raises(MangaImportError):
        read_manga_import({"format": "x", "version": 1}, SPEC, "trim", 1, 1)
    with pytest.raises(MangaImportError):
        read_manga_import(_doc(shape="star"), SPEC, "trim", 1, 1)
    with pytest.raises(MangaImportError):
        read_manga_import(_doc(points=[[0, 0], [2, 0], [1, 1]]), SPEC, "trim", 1, 1)


# ---------------------------------------------------------------- AIの関与と人の手の印


def test_AIの関与の4択で_AIの手が許されるもの():
    w = Work(ai_involvement={"name": "ai_auto", "panel_layout": "human_makes_ai_checks", "drawing": "no_ai"})
    assert all(ai_may(w, "name", a) for a in ("propose", "decide", "check"))
    assert [ai_may(w, "panel_layout", a) for a in ("propose", "decide", "check")] == [False, False, True]
    assert not any(ai_may(w, "drawing", a) for a in ("propose", "decide", "check"))
    # 選んでいない作業は設計の既定（AIが案を出し人が選ぶ）。既定であることも返す
    assert mode_of(w, "finishing") == (DESIGN_DEFAULT_MODE, False) and DESIGN_DEFAULT_MODE == "ai_proposes"
    assert [ai_may(w, "finishing", a) for a in ("propose", "decide", "check")] == [True, False, True]
    # 赤入れの項目は、行の about_task を作業とする印（ABOUT_TASK）
    assert set(TASKS) | {ABOUT_TASK} >= {t for fields in HUMAN_EDITABLE_FIELDS.values() for t in fields.values()}


def test_項目を変えるAIは_その項目の作業の関与で止まり_人は止まらない():
    w = Work(ai_involvement={"name": "ai_auto"})
    require_ai_may_change_fields(AI, w, "panels", {"content"})
    with pytest.raises(AiInvolvementRefused, match="コマ割り"):
        require_ai_may_change_fields(AI, w, "panels", {"content", "frame"})
    with pytest.raises(AiInvolvementRefused, match="仕上げ"):
        require_ai_may_change_fields(AI, w, "text_items", {"text", "font_size_pt"})
    require_ai_may_change_fields(HUMAN, Work(ai_involvement={"name": "no_ai"}), "panels", {"content"})


def test_同じ値は変更に数えない():
    row = Panel(frame={"polygon_mm": [[0, 0], [1, 0], [1, 1]], "bleeds": False}, content={"size": "大"}, order=1,
                human_hand_fields=[])
    same = {"frame": PanelFrame(polygon_mm=[(0.0, 0.0), (1, 0), (1, 1)], bleeds=False).model_dump(),
            "content": {"size": "大", "shot": None}, "order": 1}
    assert drop_unchanged(row, same) == {}
    assert drop_unchanged(row, {"order": 2}) == {"order": 2}


def test_AIの変更は人の手の所に当たる分を分けて返す():
    row = Panel(human_hand_fields=["frame"], human_confirmed=False)
    assert split_held_changes(row, {"frame": {}, "content": {}}) == ({"content": {}}, {"frame": {}})
    confirmed = Panel(human_hand_fields=[], human_confirmed=True)
    assert split_held_changes(confirmed, {"content": {}}) == ({}, {"content": {}})


# ---------------------------------------------------------------- 値の形（人もAIも同じに確かめる）


def test_文字の値の形():
    TextItemValues(item_kind="balloon", order=0, text="あ", balloon_kind="台詞", writing_direction="vertical",
                   font_size_pt=9, box_mm=(0, 0, 10, 20), tail_target_mm=(5, 30))
    with pytest.raises(ValidationError):
        TextItemValues(item_kind="drawn_sfx", order=0, text="ドン", speaker="A")
    with pytest.raises(ValidationError):
        TextItemValues(item_kind="balloon", order=0, text="あ", box_mm=(10, 0, 5, 20))
    with pytest.raises(ValidationError):
        TextItemValues(item_kind="balloon", order=0, text="あ", font_size_pt=0)


def test_絵の置き場と利用の条件の形():
    pl = ImagePlacement(crop_px=(0, 0, 100, 50), dest_box_mm=(0, 0, 150, 70))
    assert pl.fits_image(100, 50) and not pl.fits_image(99, 50)
    with pytest.raises(ValidationError):
        ImagePlacement(crop_px=(10, 0, 5, 50), dest_box_mm=(0, 0, 1, 1))
    base = dict(commercial_use="unknown", rights_holder="A", training_use="no", credit_required="yes",
                checked_on="2026-10-08")
    with pytest.raises(ValidationError, match="terms_url"):
        UsageTerms(**base)
    UsageTerms(**base, terms_url="https://example.com/terms")


def test_人の手の範囲のマスクは範囲だけ白():
    png = protected_mask_png(20, 10, [[(0, 0), (9, 0), (9, 9), (0, 9)]])
    im = Image.open(io.BytesIO(png)).convert("RGB")
    assert im.size == (20, 10)
    assert im.getpixel((2, 2)) == (255, 255, 255) and im.getpixel((15, 5)) == (0, 0, 0)
    empty = Image.open(io.BytesIO(protected_mask_png(4, 4, []))).convert("L")
    assert empty.getextrema() == (0, 0)
