"""コマの枠の形の検査（試作 p12 `check`・`recheck.py`、V3ハーネス設計 5.3・6章）。
はみ出し・重なり・隙間・極小のコマ・空き・読む順・大のコマ・左右と上下の隙間・縦線と横線のずれ・ノド・内側の枠。
読む順の検査は右から読む前提で書き、左から読む作品は枠を反転してから同じ検査にかける（reading_direction_mirror）。
「検査を通過」は形が崩れていないという意味だけで、良い割りという意味ではない（p12 で利用者が一覧を見て判定）。"""
import math

import numpy as np
from PIL import Image, ImageDraw

from v3server.name_checks.check_report_types import (
    CheckResult,
    Finding,
    Thresholds,
    fixed_rule_result,
    limit_result,
    no_data_result,
    rounded,
)
from v3server.name_structure.name_draft_schema import NameDraft, NamePage, NamePanel
from v3server.name_structure.reading_direction import PageSpec
from v3server.panel_layout.panel_geometry import (
    FLOAT_EPS,
    Box,
    box_height,
    box_inside,
    box_width,
    polygon_area,
    polygon_bbox,
    polygon_distance,
    polygon_overlap_area,
)
from v3server.panel_layout.reading_direction_mirror import (
    crosses_gutter_edge,
    facing_page_pairs,
    frame_span_width,
    occupies_two_pages,
    page_reading_sequence,
    page_sides,
    spread_gutter_x,
    to_right_to_left_polygon,
)

THRESHOLD_KEYS = {
    "panel_gap_min_mm": "コマどうしの隙間の下限（mm）",
    "panel_short_side_min_mm": "コマの短い辺の下限（mm）",
    "empty_area_max_mm2": "どのコマにも隙間にも入らない場所の上限（mm²、1ページ）",
    "row_cut_offset_min_mm": "上下の段の縦線のずれの下限（mm）",
    "facing_row_line_offset_min_mm": "向かい合う2ページの段の横線のずれの下限（mm）",
}

# 空きの面積を数えるときの、1mm あたりの画素の数。測る精度であって、判定の閾値ではない
_RASTER_PX_PER_MM = 4

_NO_FRAME = "枠の無いコマがある（コマ割りの計算の前）"


def _has_frames(draft: NameDraft) -> bool:
    return all(p.frame is not None for p in draft.all_panels())


def rtl_polygons(page: NamePage, draft: NameDraft) -> dict[int, list[tuple[float, float]]]:
    """右から読む前提の検査にかける写し。左から読む作品は左右を反転する。"""
    width = frame_span_width(page, draft.page_spec)
    return {p.n: to_right_to_left_polygon(p.frame.polygon_mm, draft.reading_direction, width) for p in page.panels}


def rtl_bboxes(page: NamePage, draft: NameDraft) -> dict[int, Box]:
    return {n: polygon_bbox(poly) for n, poly in rtl_polygons(page, draft).items()}


# ---- 番号と段（枠が無くても見られる） ----

def page_frame_regions(page: NamePage, spec: PageSpec) -> list[Box]:
    """ページの基本枠（ページの座標）。2ページ分の見開きは左右のページの基本枠の2つ。"""
    W, H = spec.frame_width_mm, spec.frame_height_mm
    if occupies_two_pages(page):
        ox, _ = spec.frame_origin_in_trim()
        return [(0.0, 0.0, W, H), (W + 2 * ox, 0.0, 2 * W + 2 * ox, H)]
    return [(0.0, 0.0, W, H)]


def intended_overlap(a: NamePanel, b: NamePanel) -> bool:
    """どちらかが、もう一方をわざと重ねるコマとして挙げているか（NamePanel.overlaps）。"""
    return (a.overlaps is not None and b.n in a.overlaps) or (b.overlaps is not None and a.n in b.overlaps)


def check_rows_order(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """段に並べた番号が、作品の通し番号どおりに1ずつ増えるか。ページのコマと段の番号が一致するか。
    試作 p12 の「段と比」では、見せ場を最後の段に置くために台本の順を入れ替えた崩れ（7回中6回）と、
    段の中を左から並べた崩れ（1回）が出た。どちらもここで見つかる。"""
    findings: list[Finding] = []
    prev: int | None = None
    for pg in draft.pages:
        seq = page_reading_sequence(pg)
        if sorted(seq) != sorted(p.n for p in pg.panels) or len(set(seq)) != len(seq):
            findings.append(Finding(page=pg.page, value=str(pg.rows), note="段に並べた番号とページのコマの番号が合わない"))
        for n in seq:
            if prev is not None and n != prev + 1:
                findings.append(Finding(page=pg.page, panel=n, value=f"{prev}の次が{n}", note="読む順の番号が1ずつ増えていない"))
            prev = n
    return fixed_rule_result("rows_order", "段に並べた読む順の番号", findings)


# ---- 枠の形 ----

def check_frame_bounds(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """断ち切りでないコマは基本枠の中、断ち切りのコマは塗り足しの外端の中に収まるか。"""
    title = "枠のはみ出し"
    if not _has_frames(draft):
        return no_data_result("frame_bounds", title, _NO_FRAME)
    spec = draft.page_spec
    H = spec.frame_height_mm
    ox, oy = spec.frame_origin_in_trim()
    findings = []
    for pg in draft.pages:
        # 2ページ分の見開きは、左のページの基本枠の左端から右のページの基本枠の右端まで（ノドをまたぐコマを許す）
        span = frame_span_width(pg, spec)
        inner: Box = (0.0, 0.0, span, H)
        outer: Box = (-ox - spec.bleed_mm, -oy - spec.bleed_mm, span + ox + spec.bleed_mm, H + oy + spec.bleed_mm)
        for p in pg.panels:
            b = polygon_bbox(p.frame.polygon_mm)
            limit = outer if p.frame.bleeds else inner
            if not box_inside(b, limit):
                where = "塗り足しの外" if p.frame.bleeds else "基本枠の外"
                findings.append(Finding(page=pg.page, panel=p.n, value=str(tuple(rounded(v) for v in b)), note=f"{where}へ出ている"))
    return fixed_rule_result("frame_bounds", title, findings)


def check_bleed_matches_shape(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """形が「断ち切り」のコマだけが基本枠の外へ伸びているか。
    コマ割りの計算は、基本枠の辺に接していないコマやノドの辺にしか接していないコマを伸ばさないので、その食い違いをここで出す。"""
    title = "断ち切りの指定と枠"
    if not _has_frames(draft):
        return no_data_result("bleed_matches_shape", title, _NO_FRAME)
    findings = []
    for pg in draft.pages:
        for p in pg.panels:
            if p.shape == "断ち切り" and not p.frame.bleeds:
                findings.append(Finding(page=pg.page, panel=p.n, note="断ち切りの指定なのに枠が外へ伸びていない"))
            elif p.shape != "断ち切り" and p.frame.bleeds:
                findings.append(Finding(page=pg.page, panel=p.n, value=p.shape, note="断ち切りの指定が無いのに枠が外へ伸びている"))
    return fixed_rule_result("bleed_matches_shape", title, findings)


def check_overlap(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """コマどうしが重なっていないか。わざと重ねるコマ（NamePanel.overlaps に挙げた組）は指摘しない。"""
    title = "コマの重なり"
    if not _has_frames(draft):
        return no_data_result("overlap", title, _NO_FRAME)
    findings = []
    for pg in draft.pages:
        ps = pg.panels
        for i, a in enumerate(ps):
            for b in ps[i + 1:]:
                if intended_overlap(a, b):
                    continue
                ov = polygon_overlap_area(a.frame.polygon_mm, b.frame.polygon_mm)
                if ov > FLOAT_EPS:
                    findings.append(Finding(page=pg.page, panel=a.n, value=rounded(ov), note=f"コマ{b.n}と重なる（mm²）"))
    return fixed_rule_result("overlap", title, findings)


def check_panel_gap(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """重なっていないコマどうしの最短の隙間。接している（0mm）ものも入る。わざと重ねる組は見ない。"""
    title = "コマどうしの隙間"
    if not _has_frames(draft):
        return no_data_result("panel_gap", title, _NO_FRAME)
    measured = []
    for pg in draft.pages:
        ps = pg.panels
        for i, a in enumerate(ps):
            for b in ps[i + 1:]:
                if intended_overlap(a, b) or polygon_overlap_area(a.frame.polygon_mm, b.frame.polygon_mm) > FLOAT_EPS:
                    continue  # 重なりは check_overlap が出す
                d = polygon_distance(a.frame.polygon_mm, b.frame.polygon_mm)
                measured.append((d, Finding(page=pg.page, panel=a.n, value=rounded(d), note=f"コマ{b.n}との隙間（mm）")))
    value = rounded(min(v for v, _ in measured)) if measured else None
    return limit_result("panel_gap", title, thresholds, "panel_gap_min_mm", "min", value, measured)


def check_tiny_panel(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """コマの短い辺（外接する四角の短い辺。斜めのコマは実際より長めに出る）。"""
    title = "極小のコマ"
    if not _has_frames(draft):
        return no_data_result("tiny_panel", title, _NO_FRAME)
    measured = []
    for pg in draft.pages:
        for p in pg.panels:
            b = polygon_bbox(p.frame.polygon_mm)
            s = min(box_width(b), box_height(b))
            measured.append((s, Finding(page=pg.page, panel=p.n, value=rounded(s), note="短い辺（mm）")))
    value = rounded(min(v for v, _ in measured)) if measured else None
    return limit_result("tiny_panel", title, thresholds, "panel_short_side_min_mm", "min", value, measured)


def _dilate(mask: np.ndarray, rx: int, ry: int) -> np.ndarray:
    """四角（横 2rx+1・縦 2ry+1）で膨らませる。"""
    def along(m: np.ndarray, r: int, axis: int) -> np.ndarray:
        if r == 0:
            return m
        c = np.cumsum(np.pad(m.astype(np.int32), [(r + 1, r) if a == axis else (0, 0) for a in range(2)]), axis=axis)
        n = m.shape[axis]
        hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
        lo = np.take(c, np.arange(0, n), axis=axis)
        return (hi - lo) > 0
    return along(along(mask, rx, 1), ry, 0)


def page_empty_area_mm2(page: NamePage, draft: NameDraft) -> float:
    """基本枠の中で、どのコマにも、コマの周りの隙間（規格の左右・上下の隙間）にも入らない面積（試作 p12 `recheck.py`）。
    コマを画素に塗り、規格の隙間の幅だけ膨らませて、塗られなかった画素を数える。2ページ分の見開きは左右の基本枠の中だけを数える。"""
    spec = draft.page_spec
    s = _RASTER_PX_PER_MM
    w, h = math.ceil(frame_span_width(page, spec) * s), math.ceil(spec.frame_height_mm * s)
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    for p in page.panels:
        d.polygon([(x * s, y * s) for x, y in p.frame.polygon_mm], fill=255)
    mask = np.asarray(img) > 0
    covered = _dilate(mask, math.ceil(spec.gutter_x_mm * s), math.ceil(spec.gutter_y_mm * s))
    region = Image.new("L", (w, h), 0)
    rd = ImageDraw.Draw(region)
    for x0, y0, x1, y1 in page_frame_regions(page, spec):
        # 右端と下端の画素を含めないよう、1画素手前までを塗る
        rd.rectangle((x0 * s, y0 * s, x1 * s - 1, y1 * s - 1), fill=255)
    inside = np.asarray(region) > 0
    return float((inside & ~covered).sum()) / (s * s)


def check_empty_space(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """空いた場所。試作 p12 では座標を直接出させた割りで24回中2回出た。"""
    title = "どのコマにも入らない場所"
    if not _has_frames(draft):
        return no_data_result("empty_space", title, _NO_FRAME)
    measured = []
    for pg in draft.pages:
        a = page_empty_area_mm2(pg, draft)
        measured.append((a, Finding(page=pg.page, value=rounded(a), note="空いた面積（mm²）")))
    value = rounded(max(v for v, _ in measured)) if measured else None
    return limit_result("empty_space", title, thresholds, "empty_area_max_mm2", "max", value, measured)


def check_frame_reading_order(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """枠の位置が、番号の順に右から左・上から下で読めるか（試作 p12 `check` の規則）。
    次のコマが前のコマより丸ごと上にある、または同じ高さの帯で前のコマより右にあれば崩れ。
    左から読む作品は反転してから同じ規則にかける。p34：向きを取り違えて検査すると48/48で崩れとして出る。"""
    title = "枠の位置の読む順"
    if not _has_frames(draft):
        return no_data_result("frame_reading_order", title, _NO_FRAME)
    findings = []
    for pg in draft.pages:
        bb = rtl_bboxes(pg, draft)
        ns = sorted(bb)
        for k, m in zip(ns, ns[1:]):
            a, b = bb[k], bb[m]
            vov = min(a[3], b[3]) - max(a[1], b[1])
            if b[3] <= a[1] + FLOAT_EPS:
                findings.append(Finding(page=pg.page, panel=m, note=f"コマ{k}より上にある"))
            elif vov > FLOAT_EPS and b[0] >= a[2] - FLOAT_EPS and b[1] >= a[1] - FLOAT_EPS:
                side = "右" if draft.reading_direction == "right_to_left" else "左"
                findings.append(Finding(page=pg.page, panel=m, note=f"コマ{k}と同じ高さで{side}にある"))
    return fixed_rule_result("frame_reading_order", title, findings)


def check_big_is_largest(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """「大」のコマが、そのページの「大」でないどのコマより広いか。"""
    title = "「大」のコマの広さ"
    if not _has_frames(draft):
        return no_data_result("big_is_largest", title, _NO_FRAME)
    findings = []
    for pg in draft.pages:
        area = {p.n: polygon_area(p.frame.polygon_mm) for p in pg.panels}
        others = [area[p.n] for p in pg.panels if p.size != "大"]
        if not others:
            continue
        top = max(others)
        for p in pg.panels:
            if p.size == "大" and area[p.n] < top - FLOAT_EPS:
                findings.append(Finding(page=pg.page, panel=p.n, value=f"{rounded(area[p.n])} < {rounded(top)}",
                                        note="「大」でないコマより狭い（mm²）"))
    return fixed_rule_result("big_is_largest", title, findings)


def check_gutter_ratio(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """左右に並ぶコマの隙間が、上下に並ぶコマの隙間より狭いか（課題8）。比べるだけなので閾値は要らない。
    各コマのいちばん近い左右の隣・上下の隣との隙間を取り、ページの左右の最大と上下の最小を比べる。"""
    title = "左右の隙間が上下より狭いか"
    if not _has_frames(draft):
        return no_data_result("gutter_ratio", title, _NO_FRAME)
    findings = []
    for pg in draft.pages:
        polys = rtl_polygons(pg, draft)
        bb = {n: polygon_bbox(q) for n, q in polys.items()}
        side_gaps, stack_gaps = [], []
        for n in polys:
            best_side = best_stack = math.inf
            for m in polys:
                if m == n:
                    continue
                a, b = bb[n], bb[m]
                yov = min(a[3], b[3]) - max(a[1], b[1])
                xov = min(a[2], b[2]) - max(a[0], b[0])
                if yov > FLOAT_EPS and xov <= FLOAT_EPS:
                    best_side = min(best_side, polygon_distance(polys[n], polys[m]))
                elif xov > FLOAT_EPS and yov <= FLOAT_EPS:
                    best_stack = min(best_stack, polygon_distance(polys[n], polys[m]))
            if best_side < math.inf:
                side_gaps.append(best_side)
            if best_stack < math.inf:
                stack_gaps.append(best_stack)
        if side_gaps and stack_gaps and max(side_gaps) >= min(stack_gaps) - FLOAT_EPS:
            findings.append(Finding(page=pg.page, value=f"左右 {rounded(max(side_gaps))} / 上下 {rounded(min(stack_gaps))}",
                                    note="左右の隙間が上下の隙間より狭くない（mm）"))
    return fixed_rule_result("gutter_ratio", title, findings)


def _row_boxes(page: NamePage, draft: NameDraft) -> list[list[Box]]:
    bb = rtl_bboxes(page, draft)
    return [[bb[n] for n in row if n in bb] for row in page.rows]


def check_row_cut_offset(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """上下に隣り合う段で、コマを分ける縦線がどれだけずれているか（5.3「縦線は段ごとにずらす」）。
    縦線の位置は、段の中で隣り合う2コマの隙間の真ん中。段に1コマしか無ければ縦線は無い。"""
    title = "上下の段の縦線のずれ"
    if not _has_frames(draft):
        return no_data_result("row_cut_offset", title, _NO_FRAME)
    measured = []
    for pg in draft.pages:
        cuts = []
        for row in _row_boxes(pg, draft):
            # 右から読む写しなので、段の中は右のコマから並ぶ
            cuts.append([(a[0] + b[2]) / 2 for a, b in zip(row, row[1:])])
        for i in range(len(cuts) - 1):
            if not cuts[i] or not cuts[i + 1]:
                continue
            off = min(abs(u - v) for u in cuts[i] for v in cuts[i + 1])
            measured.append((off, Finding(page=pg.page, value=rounded(off), note=f"{i + 1}段目と{i + 2}段目の縦線のずれ（mm）")))
    value = rounded(min(v for v, _ in measured)) if measured else None
    return limit_result("row_cut_offset", title, thresholds, "row_cut_offset_min_mm", "min", value, measured)


def check_facing_row_line_offset(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """向かい合う2ページで、段を分ける横線がどれだけずれているか（5.3「見開きの左右で横線をずらす」）。
    横線の位置は、最後の段を除く各段の下端。"""
    title = "向かい合うページの横線のずれ"
    if not _has_frames(draft):
        return no_data_result("facing_row_line_offset", title, _NO_FRAME)

    def lines(pg: NamePage) -> list[float]:
        return [max(b[3] for b in row) for row in _row_boxes(pg, draft)[:-1] if row]

    measured = []
    for i, j in facing_page_pairs(draft):
        a, b = lines(draft.pages[i]), lines(draft.pages[j])
        if not a or not b:
            continue
        off = min(abs(u - v) for u in a for v in b)
        measured.append((off, Finding(page=draft.pages[i].page, value=rounded(off),
                                      note=f"{draft.pages[j].page}ページとの横線のずれ（mm）")))
    value = rounded(min(v for v, _ in measured)) if measured else None
    return limit_result("facing_row_line_offset", title, thresholds, "facing_row_line_offset_min_mm", "min", value, measured)


# ---- ノドと内側の枠（課題29・30・158） ----

def check_gutter_side_contents(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """ノドに、断ち切り・顔・セリフが入っていないか（課題29）。基本枠のノドの辺を越えてノドの側へ出ていれば指摘。
    断ち切りは枠、顔は人物の顔の範囲、セリフは吹き出しの範囲で見る。まだ無い範囲は見ない。
    2ページ分を占める見開き（spread_occupies_two_pages）は、顔と吹き出しがノドの線をまたいでいれば指摘（コマはまたいでよい）。
    2ページ分かを決めていない見開きはノドの位置が分からないので対象外にする（値に書く）。"""
    title = "ノドの断ち切り・顔・セリフ"
    spec = draft.page_spec
    sides = page_sides(draft)
    findings = []
    looked = 0
    skipped = [pg.page for pg in draft.pages if pg.spread and not occupies_two_pages(pg)]
    for pg, side in zip(draft.pages, sides):
        if occupies_two_pages(pg):
            g = spread_gutter_x(spec)
            for p in pg.panels:
                for f in p.people:
                    if f.face_box_mm is not None:
                        looked += 1
                        if f.face_box_mm[0] < g - FLOAT_EPS and f.face_box_mm[2] > g + FLOAT_EPS:
                            findings.append(Finding(page=pg.page, panel=p.n, value=f.name, note="顔が見開きのノドをまたぐ"))
                for k, b in enumerate(p.balloons):
                    if b.box_mm is not None:
                        looked += 1
                        if b.box_mm[0] < g - FLOAT_EPS and b.box_mm[2] > g + FLOAT_EPS:
                            findings.append(Finding(page=pg.page, panel=p.n, balloon=k, note="吹き出しが見開きのノドをまたぐ"))
            continue
        if pg.spread:
            continue
        for p in pg.panels:
            if p.frame is not None and p.frame.bleeds:
                looked += 1
                if crosses_gutter_edge([x for x, _ in p.frame.polygon_mm], side, spec, FLOAT_EPS):
                    findings.append(Finding(page=pg.page, panel=p.n, note="断ち切りがノドへ出ている"))
            for f in p.people:
                if f.face_box_mm is not None:
                    looked += 1
                    if crosses_gutter_edge([f.face_box_mm[0], f.face_box_mm[2]], side, spec, FLOAT_EPS):
                        findings.append(Finding(page=pg.page, panel=p.n, value=f.name, note="顔がノドへ出ている"))
            for k, b in enumerate(p.balloons):
                if b.box_mm is not None:
                    looked += 1
                    if crosses_gutter_edge([b.box_mm[0], b.box_mm[2]], side, spec, FLOAT_EPS):
                        findings.append(Finding(page=pg.page, panel=p.n, balloon=k, note="吹き出しがノドへ出ている"))
    if looked == 0:
        return no_data_result("gutter_side_contents", title, "断ち切りの枠・顔の範囲・吹き出しの範囲がどれも無い")
    value = f"見開きの{skipped}ページは対象外" if skipped else None
    return fixed_rule_result("gutter_side_contents", title, findings, value)


def check_balloon_inside_frame(draft: NameDraft, thresholds: Thresholds) -> CheckResult:
    """吹き出しが内側の枠（基本枠）に収まるか（課題30・158）。断ち切りのコマでも同じ。
    2ページ分の見開きは、左右どちらかの基本枠に収まれば合格。"""
    title = "吹き出しが内側の枠に収まるか"
    spec = draft.page_spec
    findings = []
    looked = 0
    for pg in draft.pages:
        regions = page_frame_regions(pg, spec)
        for p in pg.panels:
            for k, b in enumerate(p.balloons):
                if b.box_mm is None:
                    continue
                looked += 1
                if not any(box_inside(b.box_mm, r) for r in regions):
                    findings.append(Finding(page=pg.page, panel=p.n, balloon=k, value=str(tuple(rounded(v) for v in b.box_mm)),
                                            note="内側の枠から出ている"))
    if looked == 0:
        return no_data_result("balloon_inside_frame", title, "吹き出しの位置がまだ無い")
    return fixed_rule_result("balloon_inside_frame", title, findings)


FRAME_SHAPE_CHECKS = [
    check_rows_order, check_frame_bounds, check_bleed_matches_shape, check_overlap, check_panel_gap, check_tiny_panel,
    check_empty_space, check_frame_reading_order, check_big_is_largest, check_gutter_ratio, check_row_cut_offset,
    check_facing_row_line_offset, check_gutter_side_contents, check_balloon_inside_frame,
]
