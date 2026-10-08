"""ページの割りの調子の検査（試作 p27 `check.py`、V3ハーネス設計 6章）。
コマ数・段の数・同じ大きさの連続・段の割りの繰り返し・大の無いページ・大・変形・断ち切りの数・見開き・1ページ目の側・ヒキとめくり。
枠の座標は使わない（ネームの宣言の大きさ・形で数える）。数で見られるのは形だけで、良し悪しは描く人の判定が要る（p27）。"""
from collections.abc import Callable

from v3server.name_checks.check_report_types import (
    Bound,
    CheckResult,
    Finding,
    Thresholds,
    count_limit_result,
    fixed_rule_result,
    limit_result,
    no_data_result,
)
from v3server.name_structure.name_draft_schema import (
    NameDraft,
    NamePage,
    NamePanel,
    PanelSize,
)
from v3server.panel_layout.reading_direction_mirror import (
    before_turn_page_indices,
    before_turn_side,
    occupies_two_pages,
    page_reading_sequence,
    page_sides,
)

THRESHOLD_KEYS = {
    "panels_per_page_max": "1ページのコマ数の上限",
    "panels_per_page_min": "1ページのコマ数の下限",
    "rows_per_page_max": "1ページの段の数の上限",
    "rows_per_page_min": "1ページの段の数の下限",
    "cells_per_row_max": "1段のコマ数の上限",
    "same_size_run_max": "同じ大きさのコマが続く数の上限",
    "same_row_pattern_next_page_max": "段の割り（段ごとのコマ数）が次のページと同じになる回数の上限（1話）",
    "pages_without_big_max": "「大」のコマが無いページの数の上限（1話）",
    "big_panels_per_page_max": "1ページの「大」のコマの数の上限",
    "deformed_panels_per_page_max": "1ページの斜めのコマの数の上限",
    "frameless_or_bleed_per_page_max": "1ページの枠なし・断ち切りのコマの数の上限",
    "talk_panel_deformed_max": "会話だけのコマで四角でないものの数の上限（1話）",
    "spreads_max": "見開きの数の上限（1話）",
}

_SIZE_RANK: dict[PanelSize, int] = {"小": 0, "中": 1, "大": 2}
# 会話だけのコマとみなす吹き出しの種類（p27 と同じ。叫び・ナレーションを含むコマは会話だけとしない）
_TALK_KINDS = {"台詞", "心の声"}


def _panel_map(draft: NameDraft) -> dict[int, NamePanel]:
    return {p.n: p for p in draft.all_panels()}


def _reading_panels(draft: NameDraft) -> list[tuple[int, NamePanel]]:
    """（ページの番号, コマ）を、段の並びの読む順で。"""
    pm = _panel_map(draft)
    return [(pg.page, pm[n]) for pg in draft.pages for n in page_reading_sequence(pg) if n in pm]


def _per_page_count(draft: NameDraft, check_id: str, title: str, thresholds: Thresholds, key: str, bound: Bound,
                    count: Callable[[NamePage], int], note: str) -> CheckResult:
    measured = [(float(count(pg)), Finding(page=pg.page, value=count(pg), note=note)) for pg in draft.pages]
    vals = [count(pg) for pg in draft.pages]
    value = (max(vals) if bound == "max" else min(vals)) if vals else None
    return limit_result(check_id, title, thresholds, key, bound, value, measured)


def check_panels_per_page(draft: NameDraft, thresholds: Thresholds) -> list[CheckResult]:
    """1ページのコマ数（課題17）。講座の値は4〜8で割れるので、上限と下限を別の閾値で持つ。"""
    return [
        _per_page_count(draft, "panels_per_page_max", "1ページのコマ数（多すぎ）", thresholds, "panels_per_page_max", "max",
                        lambda pg: len(pg.panels), "コマ数"),
        _per_page_count(draft, "panels_per_page_min", "1ページのコマ数（少なすぎ）", thresholds, "panels_per_page_min", "min",
                        lambda pg: len(pg.panels), "コマ数"),
    ]


def check_rows_per_page(draft: NameDraft, thresholds: Thresholds) -> list[CheckResult]:
    """段の数と、1段のコマ数（課題18）。"""
    out = [
        _per_page_count(draft, "rows_per_page_max", "1ページの段の数（多すぎ）", thresholds, "rows_per_page_max", "max",
                        lambda pg: len(pg.rows), "段の数"),
        _per_page_count(draft, "rows_per_page_min", "1ページの段の数（少なすぎ）", thresholds, "rows_per_page_min", "min",
                        lambda pg: len(pg.rows), "段の数"),
    ]
    measured = [(float(len(row)), Finding(page=pg.page, value=len(row), note=f"{i + 1}段目のコマ数"))
                for pg in draft.pages for i, row in enumerate(pg.rows)]
    value = max((int(v) for v, _ in measured), default=None)
    out.append(limit_result("cells_per_row_max", "1段のコマ数", thresholds, "cells_per_row_max", "max", value, measured))
    return out


def check_same_size_run(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """宣言の大きさが同じコマが、読む順に何個続くか（課題15・19）。ページをまたいで数える。
    枠の面積でのばらつきは page_monotony_metrics が見る。"""
    seq = _reading_panels(draft)
    measured = []
    i = 0
    while i < len(seq):
        j = i
        while j + 1 < len(seq) and seq[j + 1][1].size == seq[i][1].size:
            j += 1
        run = j - i + 1
        measured.append((float(run), Finding(page=seq[i][0], panel=seq[i][1].n, value=run,
                                             note=f"ここから「{seq[i][1].size}」が{run}個続く")))
        i = j + 1
    value = max((int(v) for v, _ in measured), default=None)
    return limit_result("same_size_run", "同じ大きさのコマの連続", thresholds, "same_size_run_max", "max", value, measured)


def check_same_row_pattern_next_page(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """段ごとのコマ数の並び（例：2・1・3）が次のページと同じになる回数（課題19、p27 で1〜5回）。"""
    pats = [tuple(len(r) for r in pg.rows) for pg in draft.pages]
    items = [Finding(page=draft.pages[i + 1].page, value=str(list(pats[i])), note="前のページと同じ段の割り")
             for i in range(len(pats) - 1) if pats[i] == pats[i + 1]]
    return count_limit_result("same_row_pattern_next_page", "段の割りの繰り返し", thresholds, "same_row_pattern_next_page_max", items)


def check_pages_without_big(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """「大」のコマが無いページの数（p27 で0〜4）。"""
    items = [Finding(page=pg.page, note="「大」のコマが無い") for pg in draft.pages if not any(p.size == "大" for p in pg.panels)]
    return count_limit_result("pages_without_big", "「大」の無いページ", thresholds, "pages_without_big_max", items)


def check_special_panel_counts(draft: NameDraft, thresholds: Thresholds) -> list[CheckResult]:
    """決めゴマ（大）・変形ゴマ（斜め）・枠なしと断ち切りの1ページの数（課題20・26・28）。"""
    return [
        _per_page_count(draft, "big_panels_per_page", "1ページの「大」のコマ", thresholds, "big_panels_per_page_max", "max",
                        lambda pg: sum(p.size == "大" for p in pg.panels), "「大」の数"),
        _per_page_count(draft, "deformed_panels_per_page", "1ページの斜めのコマ", thresholds, "deformed_panels_per_page_max", "max",
                        lambda pg: sum(p.shape == "斜め" for p in pg.panels), "斜めの数"),
        _per_page_count(draft, "frameless_or_bleed_per_page", "1ページの枠なし・断ち切り", thresholds,
                        "frameless_or_bleed_per_page_max", "max",
                        lambda pg: sum(p.shape in ("枠なし", "断ち切り") for p in pg.panels), "枠なし・断ち切りの数"),
    ]


def check_talk_panel_deformed(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """会話だけのコマ（吹き出しが台詞か心の声だけで、擬音が無い）で、四角でないものの数（課題26。p27 で0〜3）。"""
    items = []
    for page, p in _reading_panels(draft):
        talk = bool(p.balloons) and all(b.kind in _TALK_KINDS for b in p.balloons) and not p.sfx
        if talk and p.shape != "四角":
            items.append(Finding(page=page, panel=p.n, value=p.shape, note="会話だけのコマが四角でない"))
    return count_limit_result("talk_panel_deformed", "会話だけのコマの変形", thresholds, "talk_panel_deformed_max", items)


def check_spreads(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """見開きの数（課題59）。位置の決まり（課題58）は講座に数字が無いので、外れたときに位置を並べるだけ。"""
    items = [Finding(page=pg.page, note="見開き") for pg in draft.pages if pg.spread]
    return count_limit_result("spreads", "見開きの数", thresholds, "spreads_max", items)


def check_spread_position(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """2ページ分を占める見開きが、めくりの後の側から始まるか（課題58の位置のうち、閾値の要らない所）。
    めくりの前の側から始まると、見開きの途中でめくることになる。2ページ分かを決めていない見開きは見られない。"""
    title = "見開きの置き場"
    turn_side = before_turn_side(draft.reading_direction)
    decided = [(i, pg) for i, pg in enumerate(draft.pages) if occupies_two_pages(pg)]
    undecided = [pg.page for pg in draft.pages if pg.spread and pg.spread_occupies_two_pages is None]
    if undecided and not decided:
        return no_data_result("spread_position", title, f"見開きの{undecided}ページが2ページ分を占めるか決まっていない")
    sides = page_sides(draft)
    findings = [Finding(page=pg.page, value=sides[i], note=f"見開きがめくりの前の側（{turn_side}）から始まる")
                for i, pg in decided if sides[i] == turn_side]
    value = f"見開きの{undecided}ページは2ページ分か決まっていないので対象外" if undecided else None
    return fixed_rule_result("spread_position", title, findings, value)


def check_first_page_side(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """1ページ目が、めくりの前の側（右から読む本は左、左から読む本は右）にあるか（課題57。p34 で向きにより入れ替わる）。"""
    want = before_turn_side(draft.reading_direction)
    got = page_sides(draft)[0] if draft.pages else None
    findings = [] if got == want else [Finding(page=draft.pages[0].page, value=got, note=f"1ページ目が{want}のページでない")]
    return fixed_rule_result("first_page_side", "1ページ目の置き場", findings)


def _last_panel(draft: NameDraft, idx: int) -> NamePanel:
    pg = draft.pages[idx]
    pm = {p.n: p for p in pg.panels}
    return pm[page_reading_sequence(pg)[-1]]


def _first_panel(draft: NameDraft, idx: int) -> NamePanel:
    pg = draft.pages[idx]
    pm = {p.n: p for p in pg.panels}
    return pm[page_reading_sequence(pg)[0]]


def check_hook_at_turn(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """めくりの前のページの最後のコマにヒキがあるか（課題49）。p27 では全部に付いた。"""
    side = before_turn_side(draft.reading_direction)
    findings = []
    for i in before_turn_page_indices(draft):
        last = _last_panel(draft, i)
        if not last.hook:
            findings.append(Finding(page=draft.pages[i].page, panel=last.n, note=f"{side}のページの最後のコマにヒキが無い"))
    return fixed_rule_result("hook_at_turn", "めくりの前のヒキ", findings)


def check_hook_position(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """ヒキの印が、めくりの前のページの最後のコマか、話の最後のコマにだけ付いているか。"""
    allowed = {_last_panel(draft, i).n for i in before_turn_page_indices(draft)}
    if draft.pages:
        allowed.add(_last_panel(draft, len(draft.pages) - 1).n)
    side = before_turn_side(draft.reading_direction)
    findings = [Finding(page=page, panel=p.n, note=f"ヒキが{side}のページの最後でない所にある")
                for page, p in _reading_panels(draft) if p.hook and p.n not in allowed]
    return fixed_rule_result("hook_position", "ヒキの位置", findings)


def check_turn_panel_size(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """めくった直後の最初のコマが「小」でないか（課題50）、めくりの前のヒキのコマより小さくないか（課題51）。宣言の大きさで比べる。"""
    findings = []
    for i in before_turn_page_indices(draft):
        hook, turn = _last_panel(draft, i), _first_panel(draft, i + 1)
        page = draft.pages[i + 1].page
        if turn.size == "小":
            findings.append(Finding(page=page, panel=turn.n, value=turn.size, note="めくった直後のコマが小さい"))
        elif _SIZE_RANK[turn.size] < _SIZE_RANK[hook.size]:
            findings.append(Finding(page=page, panel=turn.n, value=f"{turn.size} < ヒキ{hook.n}の{hook.size}",
                                    note="めくった直後のコマがヒキのコマより小さい"))
    return fixed_rule_result("turn_panel_size", "めくりのコマの大きさ", findings)


def run_page_rhythm_checks(draft: NameDraft, thresholds: Thresholds) -> list[CheckResult]:
    out: list[CheckResult] = []
    out += check_panels_per_page(draft, thresholds)
    out += check_rows_per_page(draft, thresholds)
    out.append(check_same_size_run(draft, thresholds))
    out.append(check_same_row_pattern_next_page(draft, thresholds))
    out.append(check_pages_without_big(draft, thresholds))
    out += check_special_panel_counts(draft, thresholds)
    out.append(check_talk_panel_deformed(draft, thresholds))
    out.append(check_spreads(draft, thresholds))
    out.append(check_spread_position(draft, thresholds))
    out.append(check_first_page_side(draft, thresholds))
    out.append(check_hook_at_turn(draft, thresholds))
    out.append(check_hook_position(draft, thresholds))
    out.append(check_turn_panel_size(draft, thresholds))
    return out
