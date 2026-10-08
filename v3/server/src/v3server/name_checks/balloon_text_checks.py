"""吹き出しの検査（試作 p27 `check.py`、V3ハーネス設計 6章）。
文字数・行数・数（課題159・237）と、配置の後にだけ見られる順と交差（課題153・154）。"""
from v3server.name_checks.check_report_types import (
    CheckResult,
    Finding,
    Thresholds,
    fixed_rule_result,
    limit_result,
    no_data_result,
    rounded,
)
from v3server.name_structure.name_draft_schema import NameDraft
from v3server.panel_layout.panel_geometry import FLOAT_EPS, ellipse_overlap_area
from v3server.panel_layout.reading_direction_mirror import (
    frame_span_width,
    to_right_to_left_box,
)

THRESHOLD_KEYS = {
    "balloon_chars_max": "吹き出し1つの文字数の上限（改行と空白は数えない）",
    "balloon_lines_max": "吹き出し1つの行数の上限",
    "balloons_per_panel_max": "1コマの吹き出しの数の上限",
    "balloons_per_page_max": "1ページの吹き出しの数の上限",
    "page_chars_max": "1ページのセリフの文字数の上限",
}


def balloon_chars(text: str) -> int:
    """数える文字数。改行と空白は数えない。"""
    return sum(1 for ch in text if not ch.isspace())


def check_balloon_chars(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """吹き出し1つの文字数（課題159。p27 で最大22〜58字）。"""
    measured = [(float(balloon_chars(b.text)), Finding(page=pg.page, panel=p.n, balloon=k, value=balloon_chars(b.text), note="文字数"))
                for pg in draft.pages for p in pg.panels for k, b in enumerate(p.balloons)]
    value = max((int(v) for v, _ in measured), default=None)
    return limit_result("balloon_chars", "吹き出しの文字数", thresholds, "balloon_chars_max", "max", value, measured)


def check_balloon_lines(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """吹き出し1つの行数（課題237）。改行で区切った行の数。改行の無いセリフは1行になる。"""
    measured = [(float(len(b.text.splitlines()) or 1), Finding(page=pg.page, panel=p.n, balloon=k,
                                                                value=len(b.text.splitlines()) or 1, note="行数"))
                for pg in draft.pages for p in pg.panels for k, b in enumerate(p.balloons)]
    value = max((int(v) for v, _ in measured), default=None)
    return limit_result("balloon_lines", "吹き出しの行数", thresholds, "balloon_lines_max", "max", value, measured)


def check_balloons_per_panel(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    measured = [(float(len(p.balloons)), Finding(page=pg.page, panel=p.n, value=len(p.balloons), note="吹き出しの数"))
                for pg in draft.pages for p in pg.panels]
    value = max((int(v) for v, _ in measured), default=None)
    return limit_result("balloons_per_panel", "1コマの吹き出しの数", thresholds, "balloons_per_panel_max", "max", value, measured)


def check_balloons_per_page(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    measured = []
    for pg in draft.pages:
        n = sum(len(p.balloons) for p in pg.panels)
        measured.append((float(n), Finding(page=pg.page, value=n, note="吹き出しの数")))
    value = max((int(v) for v, _ in measured), default=None)
    return limit_result("balloons_per_page", "1ページの吹き出しの数", thresholds, "balloons_per_page_max", "max", value, measured)


def check_page_chars(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """1ページのセリフの文字数（課題159：400字詰め原稿用紙の半分程度という講座の値がある）。"""
    measured = []
    for pg in draft.pages:
        n = sum(balloon_chars(b.text) for p in pg.panels for b in p.balloons)
        measured.append((float(n), Finding(page=pg.page, value=n, note="セリフの文字数")))
    value = max((int(v) for v, _ in measured), default=None)
    return limit_result("page_chars", "1ページのセリフの文字数", thresholds, "page_chars_max", "max", value, measured)


def check_balloon_order(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """1コマの中の吹き出しが、並びの順に右から左・上から下で置かれているか（課題154）。
    コマの読む順の規則（frame_shape_checks.check_frame_reading_order）を吹き出しの四角に当てる。ただしコマの規則にある
    「次の上端が前の上端より下」の条件は付けない（吹き出しでは、高さが重なって右にあれば上下によらず崩れとみなす）。
    左から読む作品は反転してから見る。コマをまたぐ順はコマの読む順に従うので、ここでは見ない。
    試作 p31：枠だけで順が決まらない格子では、列をまたぐ吹き出しがあっても12回中11回は横に読んだ（吹き出しで読む順を変えにくい）。"""
    title = "吹き出しの順"
    findings = []
    looked = 0
    for pg in draft.pages:
        width = frame_span_width(pg, draft.page_spec)
        for p in pg.panels:
            placed = [(k, to_right_to_left_box(b.box_mm, draft.reading_direction, width))
                      for k, b in enumerate(p.balloons) if b.box_mm is not None]
            for (_, a), (kb, b) in zip(placed, placed[1:], strict=False):
                looked += 1
                vov = min(a[3], b[3]) - max(a[1], b[1])
                if b[3] <= a[1] + FLOAT_EPS:
                    findings.append(Finding(page=pg.page, panel=p.n, balloon=kb, note="前の吹き出しより上にある"))
                elif vov > FLOAT_EPS and b[0] >= a[2] - FLOAT_EPS:
                    side = "右" if draft.reading_direction == "right_to_left" else "左"
                    findings.append(Finding(page=pg.page, panel=p.n, balloon=kb, note=f"前の吹き出しと同じ高さで{side}にある"))
    if looked == 0:
        return no_data_result("balloon_order", title, "位置のある吹き出しが2つ以上あるコマが無い")
    return fixed_rule_result("balloon_order", title, findings)


def check_balloon_crossing(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """同じページの吹き出しの楕円どうしが重なっていないか（課題153）。
    同じコマの1つ前の吹き出しとわざとつなげたもの（Balloon.joined_to_previous が True）の組は指摘しない。"""
    title = "吹き出しの交差"
    findings = []
    looked = 0
    for pg in draft.pages:
        placed = [(p.n, k, b.box_mm) for p in pg.panels for k, b in enumerate(p.balloons) if b.box_mm is not None]
        joined = {(p.n, k) for p in pg.panels for k, b in enumerate(p.balloons) if k > 0 and b.joined_to_previous is True}
        for i, (na, ka, a) in enumerate(placed):
            for nb, kb, b in placed[i + 1:]:
                looked += 1
                # つなげた組も見た数に入れる。見たうえで指摘しない
                if na == nb and kb == ka + 1 and (nb, kb) in joined:
                    continue
                ov = ellipse_overlap_area(a, b)
                if ov > FLOAT_EPS:
                    findings.append(Finding(page=pg.page, panel=na, balloon=ka, value=rounded(ov),
                                            note=f"コマ{nb}の吹き出し{kb + 1}と重なる（mm²）"))
    if looked == 0:
        return no_data_result("balloon_crossing", title, "位置のある吹き出しが同じページに2つ以上無い")
    return fixed_rule_result("balloon_crossing", title, findings)


BALLOON_TEXT_CHECKS = [
    check_balloon_chars, check_balloon_lines, check_balloons_per_panel, check_balloons_per_page, check_page_chars,
    check_balloon_order, check_balloon_crossing,
]
