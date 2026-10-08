"""閾値を受け取って、ネームの検査を全部回す（V3ハーネス設計 6章・7章）。
閾値は呼ぶ側が Threshold の表から読んで辞書で渡す。渡されていない検査は「閾値未設定」として値だけ返し、合否を出さない。
閾値の要らない検査（6章の表で「要らない」）は合否を出す。枠・人物の位置・吹き出しの位置が無いと計算できない検査は「データなし」。

人が作ったネームも、AIが作ったネームも、取り込んだネームも、ここで同じ検査にかける。誰が作ったかは見ない。
違うのは「未定の項目」があるかだけ（人が枠だけ描いた・取り込んだネーム）。未定の項目を使う検査は回さず、
「データなし」と未定の場所を返す。どの検査がどの項目を使うかは、下の CHECKS の1か所にだけ書く。"""
from collections.abc import Callable
from dataclasses import dataclass

from v3server.name_checks import (
    balloon_text_checks as bt,
)
from v3server.name_checks import (
    frame_shape_checks as fs,
)
from v3server.name_checks import (
    page_monotony_metrics as pm,
)
from v3server.name_checks import (
    page_rhythm_checks as pr,
)
from v3server.name_checks import (
    shot_sequence_checks as ss,
)
from v3server.name_checks.balloon_face_overlap import THRESHOLD_KEYS as FACE_KEYS
from v3server.name_checks.balloon_face_overlap import check_balloon_face_overlap
from v3server.name_checks.check_report_types import (
    CheckReport,
    CheckResult,
    Thresholds,
    no_data_result,
)
from v3server.name_structure.name_draft_schema import NameDraft

# 閾値の鍵と、その意味。画面と Threshold の表の行はこの鍵で引く
ALL_THRESHOLD_KEYS: dict[str, str] = {
    **fs.THRESHOLD_KEYS,
    **pr.THRESHOLD_KEYS,
    **ss.THRESHOLD_KEYS,
    **bt.THRESHOLD_KEYS,
    **pm.THRESHOLD_KEYS,
    **FACE_KEYS,
}

CheckFn = Callable[[NameDraft, Thresholds], CheckResult | list[CheckResult]]


@dataclass(frozen=True)
class CheckEntry:
    """検査1つ（結果を複数返すものもある）。needs は使う項目（NameDraft.undecided_fields の名前）。
    ids は返す結果の (check_id, 題)。未定の項目があって回さないときに「データなし」を返すのに使う。
    ids と検査が実際に返す check_id が合っていることは tests/unit/test_human_ai_handover_units.py で確かめる。"""

    fn: CheckFn
    needs: frozenset[str]
    ids: tuple[tuple[str, str], ...]


def _e(fn: CheckFn, needs: set[str], *ids: tuple[str, str]) -> CheckEntry:
    return CheckEntry(fn, frozenset(needs), ids)


CHECKS: list[CheckEntry] = [
    # 枠の形（frame_shape_checks）
    _e(fs.check_rows_order, {"rows"}, ("rows_order", "段に並べた読む順の番号")),
    _e(fs.check_frame_bounds, set(), ("frame_bounds", "枠のはみ出し")),
    _e(fs.check_bleed_matches_shape, {"shape"}, ("bleed_matches_shape", "断ち切りの指定と枠")),
    _e(fs.check_overlap, set(), ("overlap", "コマの重なり")),
    _e(fs.check_panel_gap, set(), ("panel_gap", "コマどうしの隙間")),
    _e(fs.check_tiny_panel, set(), ("tiny_panel", "極小のコマ")),
    _e(fs.check_empty_space, {"shape"}, ("empty_space", "どのコマにも入らない場所")),
    _e(fs.check_frame_reading_order, set(), ("frame_reading_order", "枠の位置の読む順")),
    _e(fs.check_big_is_largest, {"size"}, ("big_is_largest", "「大」のコマの広さ")),
    _e(fs.check_gutter_ratio, set(), ("gutter_ratio", "左右の隙間が上下より狭いか")),
    _e(fs.check_row_cut_offset, {"rows"}, ("row_cut_offset", "上下の段の縦線のずれ")),
    _e(fs.check_facing_row_line_offset, {"rows"}, ("facing_row_line_offset", "向かい合うページの横線のずれ")),
    _e(fs.check_gutter_side_contents, {"people", "balloons"}, ("gutter_side_contents", "ノドの断ち切り・顔・セリフ")),
    _e(fs.check_balloon_inside_frame, {"balloons"}, ("balloon_inside_frame", "吹き出しが内側の枠に収まるか")),
    # ページの調子（page_rhythm_checks）
    _e(pr.check_panels_per_page, set(), ("panels_per_page_max", "1ページのコマ数（多すぎ）"),
       ("panels_per_page_min", "1ページのコマ数（少なすぎ）")),
    _e(pr.check_rows_per_page, {"rows"}, ("rows_per_page_max", "1ページの段の数（多すぎ）"),
       ("rows_per_page_min", "1ページの段の数（少なすぎ）"), ("cells_per_row_max", "1段のコマ数")),
    _e(pr.check_same_size_run, {"size"}, ("same_size_run", "同じ大きさのコマの連続")),
    _e(pr.check_same_row_pattern_next_page, {"rows"}, ("same_row_pattern_next_page", "段の割りの繰り返し")),
    _e(pr.check_pages_without_big, {"size"}, ("pages_without_big", "「大」の無いページ")),
    _e(pr.check_special_panel_counts, {"size", "shape"}, ("big_panels_per_page", "1ページの「大」のコマ"),
       ("deformed_panels_per_page", "1ページの斜めのコマ"), ("frameless_or_bleed_per_page", "1ページの枠なし・断ち切り")),
    _e(pr.check_talk_panel_deformed, {"balloons", "balloons.kind", "sfx", "shape"},
       ("talk_panel_deformed", "会話だけのコマの変形")),
    _e(pr.check_spreads, set(), ("spreads", "見開きの数")),
    _e(pr.check_spread_position, set(), ("spread_position", "見開きの置き場")),
    _e(pr.check_first_page_side, set(), ("first_page_side", "1ページ目の置き場")),
    _e(pr.check_hook_at_turn, {"hook"}, ("hook_at_turn", "めくりの前のヒキ")),
    _e(pr.check_hook_position, {"hook"}, ("hook_position", "ヒキの位置")),
    _e(pr.check_turn_panel_size, {"size"}, ("turn_panel_size", "めくりのコマの大きさ")),
    # 写す範囲と角度の並び（shot_sequence_checks）
    _e(ss.check_same_shot_angle_next, {"shot", "angle"}, ("same_shot_angle_next", "同じ範囲・角度の連続")),
    _e(ss.check_close_shot_run, {"shot"}, ("close_shot_run", "寄りの連続")),
    _e(ss.check_full_body_interval, {"shot"}, ("full_body_interval", "全身のコマの間隔")),
    _e(ss.check_shot_classes_per_scene, {"shot", "scene"}, ("shot_classes_per_scene", "場面の中の距離の組み合わせ")),
    _e(ss.check_place_shown, {"shot", "background", "scene"}, ("place_shown", "場所を見せるコマ")),
    _e(ss.check_unusual_angle_ratio, {"angle"}, ("unusual_angle_ratio", "目の高さ以外の角度の割合")),
    _e(ss.check_characters, {"people"}, ("characters", "登場人物の数")),
    _e(ss.check_people_per_panel, {"people"}, ("people_per_panel", "1コマの人物の数")),
    _e(ss.check_conversation_sides, {"people", "scene"}, ("conversation_sides", "会話する2人の左右")),
    # 吹き出しと文字（balloon_text_checks）
    _e(bt.check_balloon_chars, {"balloons"}, ("balloon_chars", "吹き出しの文字数")),
    _e(bt.check_balloon_lines, {"balloons"}, ("balloon_lines", "吹き出しの行数")),
    _e(bt.check_balloons_per_panel, {"balloons"}, ("balloons_per_panel", "1コマの吹き出しの数")),
    _e(bt.check_balloons_per_page, {"balloons"}, ("balloons_per_page", "1ページの吹き出しの数")),
    _e(bt.check_page_chars, {"balloons"}, ("page_chars", "1ページのセリフの文字数")),
    _e(bt.check_balloon_order, {"balloons"}, ("balloon_order", "吹き出しの順")),
    _e(bt.check_balloon_crossing, {"balloons"}, ("balloon_crossing", "吹き出しの交差")),
    # ページをまたいだ単調さ（page_monotony_metrics）。枠だけを見る
    _e(pm.run_monotony_checks, set(), ("area_cv_median", "面積のばらつき（中央値）"),
       ("area_max_min_median", "大小の差（中央値）"), ("single_shape_page_ratio", "形が1種類のページの割合"),
       ("full_width_ratio_median", "幅いっぱいのコマの割合（中央値）"),
       ("top_aligned_ratio_median", "上の辺が揃うコマの割合（中央値）")),
    _e(check_balloon_face_overlap, {"people", "balloons"}, ("balloon_face_overlap", "吹き出しが顔を隠す割合")),
]


def _undecided_reason(missing: list[str], undecided: dict[str, list[str]]) -> str:
    parts = []
    for field in missing:
        where = undecided[field]
        head = "・".join(where[:3])
        more = f" ほか{len(where) - 3}か所" if len(where) > 3 else ""
        parts.append(f"{field}（{head}{more}）")
    return "未定の項目がある: " + "、".join(parts)


def run_name_checks(draft: NameDraft, thresholds: Thresholds) -> CheckReport:
    """全部の検査を回す。知らない閾値の鍵が渡されたら、書き間違いを見落とさないよう例外にする。"""
    unknown = sorted(set(thresholds) - set(ALL_THRESHOLD_KEYS))
    if unknown:
        raise KeyError(f"知らない閾値の鍵 {unknown}")
    undecided = draft.undecided_fields()
    results: list[CheckResult] = []
    for entry in CHECKS:
        missing = sorted(entry.needs & set(undecided))
        if missing:
            reason = _undecided_reason(missing, undecided)
            results += [no_data_result(cid, title, reason) for cid, title in entry.ids]
            continue
        out = entry.fn(draft, thresholds)
        results += out if isinstance(out, list) else [out]
    return CheckReport(results=results)
