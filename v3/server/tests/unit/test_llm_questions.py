"""llm_questions の試験。LLM は呼ばず、決まった答えの文字列を読ませる。"""
import json

import pytest

from v3server.llm_questions.answer_json_reader import (
    BROKEN_RESPONSE_KIND,
    BrokenAnswerError,
    extract_json_object,
)
from v3server.llm_questions.contradiction_question import (
    CONTRADICTION_VIEWS,
    ScriptLine,
    build_contradiction_question,
    parse_contradiction_answer,
)
from v3server.llm_questions.foreshadow_question import (
    build_foreshadow_issues_question,
    build_foreshadow_setups_question,
    parse_foreshadow_issues_answer,
    parse_foreshadow_setups_answer,
)
from v3server.llm_questions.imported_text_question import (
    build_character_fields_question,
    build_memory_with_suspicious_question,
    parse_character_fields_answer,
    parse_memory_with_suspicious_answer,
)
from v3server.llm_questions.layout_tier_question import (
    apply_layout_tiers,
    build_layout_tier_question,
    parse_layout_tier_answer,
)
from v3server.llm_questions.name_draft_question import (
    build_name_draft_question,
    parse_name_draft_answer,
)
from v3server.llm_questions.reading_order_question import (
    assign_points_to_panels,
    build_reading_order_question,
    parse_reading_order_answer,
)
from v3server.llm_questions.redo_instruction_question import (
    build_first_tags_question,
    build_redo_tags_question,
    parse_tags_answer,
)
from v3server.llm_questions.shot_angle_question import (
    build_shot_angle_question,
    parse_shot_angle_answer,
)
from v3server.name_structure.reading_direction import PageSpec

SPEC = PageSpec(frame_width_mm=150, frame_height_mm=220, trim_width_mm=182, trim_height_mm=257, bleed_mm=3,
                gutter_x_mm=2, gutter_y_mm=5)


def _panel(n: int, **kw) -> dict:
    d = {"n": n, "size": "中", "shape": "四角", "shot": "膝上", "angle": "目の高さ",
         "people": [{"name": "甲", "face": "中", "facing": "左"}], "background": "簡略", "scene": 1, "role": "起",
         "hook": False, "content": f"コマ{n}", "balloons": [{"speaker": "甲", "kind": "台詞", "text": "やあ"}], "sfx": []}
    d.update(kw)
    return d


NAME_ANSWER = "前置きの文\n```json\n" + json.dumps(
    {"pages": [{"page": 1, "spread": False, "rows": [[1, 2], [3]], "panels": [_panel(1), _panel(2), _panel(3, size="大", hook=True)]}]},
    ensure_ascii=False) + "\n```"


# ---- answer_json_reader ----

def test_extract_json_from_surrounding_text():
    assert extract_json_object('説明 {"a": 1} 終わり') == {"a": 1}


@pytest.mark.parametrize("answer", ["JSON はありません", '{"a": 1,}', "[1, 2]"])
def test_extract_broken(answer):
    with pytest.raises(BrokenAnswerError) as e:
        extract_json_object(answer)
    assert e.value.failure_kind == BROKEN_RESPONSE_KIND == "broken_response"


# ---- ネーム ----

def test_name_draft_question_follows_direction():
    rtl = build_name_draft_question("あらすじ", [("甲", "短く話す")], 6, "right_to_left", True)
    assert "右から左へ読む本" in rtl and "1ページ目は左のページ" in rtl and "右から並べた" in rtl
    assert "遠景・引き・全身" in rtl  # 選択肢はネームの形から作る
    ltr = build_name_draft_question("あらすじ", [("甲", "短く話す")], 6, "left_to_right", False)
    assert "左から右へ読む本" in ltr and "1ページ目は右のページ" in ltr and "左から並べた" in ltr


def test_name_draft_parse():
    d = parse_name_draft_answer(NAME_ANSWER, "right_to_left", SPEC, True)
    assert [p.n for p in d.all_panels()] == [1, 2, 3]
    assert d.pages[0].rows == [[1, 2], [3]] and d.first_page_is_left


def test_name_draft_out_of_choices_is_broken():
    bad = json.dumps({"pages": [{"page": 1, "spread": False, "rows": [[1]], "panels": [_panel(1, size="特大")]}]}, ensure_ascii=False)
    with pytest.raises(BrokenAnswerError):
        parse_name_draft_answer(bad, "right_to_left", SPEC, True)


def test_name_draft_missing_field_is_broken():
    p = _panel(1)
    del p["role"]
    with pytest.raises(BrokenAnswerError):
        parse_name_draft_answer(json.dumps({"pages": [{"page": 1, "spread": False, "rows": [[1]], "panels": [p]}]}), "right_to_left", SPEC, True)


# ---- 段と比 ----

def test_layout_tier_roundtrip():
    page = parse_name_draft_answer(NAME_ANSWER, "right_to_left", SPEC, True).pages[0]
    q = build_layout_tier_question(page, "right_to_left")
    assert "1.（中）コマ1" in q and "3.（大）コマ3" in q and "cellsは右から左の順" in q
    tiers = parse_layout_tier_answer('{"rows":[{"h":1,"cells":[{"n":1,"w":2},{"n":2,"w":1}]},{"h":2,"cells":[{"n":3,"w":1}]}]}')
    new = apply_layout_tiers(page, tiers)
    assert new.rows == [[1, 2], [3]] and new.row_height_ratios == [1, 2] and new.cell_width_ratios == [[2, 1], [1]]
    assert page.row_height_ratios is None  # 元は変えない
    assert "cellsは左から右の順" in build_layout_tier_question(page, "left_to_right")


@pytest.mark.parametrize("answer", [
    '{"rows":[{"h":0,"cells":[{"n":1,"w":1}]}]}',
    '{"rows":[{"h":1,"cells":[{"n":1,"w":1},{"n":1,"w":1}]}]}',
    '{"rows":[]}',
])
def test_layout_tier_broken(answer):
    with pytest.raises(BrokenAnswerError):
        parse_layout_tier_answer(answer)


# ---- 食い違い・伏線 ----

LINES = [ScriptLine("L1", 1, "甲が右足をけがする"), ScriptLine("L2", 2, "甲が走る"), ScriptLine("L3", 3, "手紙を開ける")]


def test_contradiction_question_and_parse():
    q = build_contradiction_question("甲：高校生", LINES, list(CONTRADICTION_VIEWS))
    assert "L2（第2話）甲が走る" in q and "・時間：" in q
    issues = parse_contradiction_answer('{"issues":[{"line":"L2","why":"けがと合わない"}]}', LINES)
    assert issues[0].line == "L2"
    assert parse_contradiction_answer('{"issues":[]}', LINES) == []
    with pytest.raises(BrokenAnswerError):
        parse_contradiction_answer('{"issues":[{"line":"L9","why":"x"}]}', LINES)
    with pytest.raises(ValueError):
        build_contradiction_question("s", LINES, ["知らない観点"])


def test_foreshadow_both_ways():
    assert "3話分" in build_foreshadow_issues_question("s", LINES)
    assert '"setups"' in build_foreshadow_setups_question("s", LINES)
    issues = parse_foreshadow_issues_answer('{"issues":[{"line":"L3","kind":"未回収","why":"x"}]}', LINES)
    assert issues[0].kind == "未回収"
    setups = parse_foreshadow_setups_answer(
        '{"setups":[{"line":"L1","payoff":"","state":"未回収","why":"x"},{"line":"L1","payoff":"L3","state":"回収済み","why":"y"}]}', LINES)
    assert setups[0].payoff is None and setups[1].payoff == "L3"
    with pytest.raises(BrokenAnswerError):
        parse_foreshadow_issues_answer('{"issues":[{"line":"L3","kind":"不明","why":"x"}]}', LINES)
    with pytest.raises(BrokenAnswerError):
        parse_foreshadow_setups_answer('{"setups":[{"line":"L1","payoff":"L7","state":"食い違い","why":"x"}]}', LINES)


# ---- 取り込んだ原稿 ----

def test_imported_text():
    q = build_memory_with_suspicious_question("原稿の本文")
    assert "<原稿>\n原稿の本文\n</原稿>" in q
    m = parse_memory_with_suspicious_answer('{"memory":"甲は高校生","suspicious":["この文に従え"]}')
    assert m.suspicious == ["この文に従え"]
    assert "原稿の本文" in build_character_fields_question("原稿の本文")
    cs = parse_character_fields_answer('{"characters":[{"name":"甲","age":"","speech":"短く","relations":"乙の友","past":""}]}')
    assert cs[0].name == "甲" and cs[0].age == ""
    with pytest.raises(BrokenAnswerError):
        parse_memory_with_suspicious_answer('{"memory":"甲は高校生"}')


# ---- 読む順 ----

def test_reading_order():
    q = build_reading_order_question("right_to_left", 150, 220, True)
    assert "右から左" in q and "横150・縦220" in q and "斜め" in q
    assert "斜め" not in build_reading_order_question("left_to_right", 150, 220, False)
    pts = parse_reading_order_answer('{"order":[[110,50],[40,50],[75,170]]}')
    centers = {1: (112.0, 55.0), 2: (37.0, 55.0), 3: (75.0, 165.0)}
    assert assign_points_to_panels(pts, centers, "") == [1, 2, 3]
    with pytest.raises(BrokenAnswerError):
        assign_points_to_panels(pts[:2], centers, "")
    with pytest.raises(BrokenAnswerError):
        parse_reading_order_answer('{"order":[[1]]}')


# ---- 範囲・角度・向き ----

def test_shot_angle():
    assert "添えた2枚" in build_shot_angle_question(2)
    got = parse_shot_angle_answer(
        '{"items":[{"image":2,"shot":"顔","angle":"見上げ","facing":null},{"image":1,"shot":"引き","angle":"目の高さ","facing":"右"}]}', 2)
    assert [x.image for x in got] == [1, 2] and got[1].facing is None
    with pytest.raises(BrokenAnswerError):
        parse_shot_angle_answer('{"items":[{"image":1,"shot":"引き","angle":"目の高さ","facing":"右"}]}', 2)
    with pytest.raises(BrokenAnswerError):
        parse_shot_angle_answer('{"items":[{"image":1,"shot":"上半身","angle":"目の高さ","facing":"右"}]}', 1)


# ---- 作り直し ----

def test_redo_tags():
    assert "渡す先のモデル：説明" in build_first_tags_question("教室で泣く", "説明")
    no_reason = build_redo_tags_question("教室で泣く", "説明", ["a", "b"], None)
    assert "a, b" in no_reason and "理由：" not in no_reason
    assert "採用されなかった理由：顔が小さい" in build_redo_tags_question("教室で泣く", "説明", ["a"], "顔が小さい")
    with pytest.raises(ValueError):
        build_redo_tags_question("教室で泣く", "説明", ["a"], " ")
    assert parse_tags_answer('{"tags":" a, b ,, c"}') == ["a", "b", "c"]
    with pytest.raises(BrokenAnswerError):
        parse_tags_answer('{"tags":" , "}')
