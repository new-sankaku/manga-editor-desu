"""段と比の割りを制約で解く（kiwisolver。試作 p50）。人が決めた枠を固定し、残りのコマが比を保って追従する。
AIが段と比を決め、人がコマ枠の道具で一部の枠を引く、のどちらからでも同じ計算で割りを作る（利用者の指示 2026-10-08）。
人の手の印（行の human_hand_fields）はここでは見ない。呼ぶ側が「固定する枠」を pinned で渡す。

制約の強さ（p50 と同じ）：
- 必須：基本枠の辺・段の間と左右の隙間・コマの最小の大きさ。必須どうしが両立しなければ例外（LayoutConflictError）。
- 強：人が固定した枠。
- 中：段の高さの比・コマの幅の比（固定した枠のある段の高さの比と、固定したコマの幅の比は外す。p50 の「除外あり」）。
p50：強・中の制約は、勝てないときに例外を出さずに静かに崩れる（強い固定400→104、強い固定2つ→2つ目が崩れた、中の比が最小20に負けた）。
そのため、指定どおりにならなかったコマを broken に必ず入れて返す。
斜めの区切りは、傾きを定数にした線形制約で書ける範囲だけ扱う（p50：角度を変数にすると隙間の補正 sqrt(1+k²) が非線形になる）。
出力の枠の形は tier_ratio_layout と同じ（PanelFrame。断ち切りは同じ規則でノド以外の辺を塗り足しまで伸ばす）。"""
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from kiwisolver import Expression, Solver, UnsatisfiableConstraint, Variable, strength

from v3server.name_structure.name_draft_schema import NameDraft, NamePage, PanelFrame
from v3server.name_structure.reading_direction import PageSpec, ReadingDirection
from v3server.panel_layout.panel_geometry import Box, polygon_bbox
from v3server.panel_layout.reading_direction_mirror import PageSide, page_sides
from v3server.panel_layout.tier_ratio_layout import (
    LayoutInputError,
    validate_tier_input,
)

# 解いた値と指定の値を比べるときの誤差の幅（mm）。解く計算の精度であって、判定の閾値ではない
_SOLVE_TOL = 1e-6


class LayoutConflictError(LayoutInputError):
    """必須の制約どうしが両立しない（例：段が多すぎて最小の大きさに収まらない）。"""


@dataclass(frozen=True)
class BrokenConstraint:
    """指定どおりにならなかったコマ1つ。kind は崩れた制約の種類。"""

    page: int
    panel: int
    kind: Literal["固定した枠", "高さの比", "幅の比"]
    wanted: str
    got: str


@dataclass(frozen=True)
class ConstrainedPageLayout:
    frames: dict[int, PanelFrame]
    broken: list[BrokenConstraint]


@dataclass
class _Cell:
    n: int
    row: int
    ratio: float
    left_top: Expression | float
    left_k: float
    right_top: Expression | float
    right_k: float


def _fmt(b: Box) -> str:
    return str(tuple(round(v, 3) for v in b))


def _clip_to_frame(b: Box, spec: PageSpec) -> Box:
    """断ち切りで外へ出た枠を、基本枠の中で解くために基本枠へ切り詰める。"""
    return max(b[0], 0.0), max(b[1], 0.0), min(b[2], spec.frame_width_mm), min(b[3], spec.frame_height_mm)


def _visual_slants(page: NamePage, direction: ReadingDirection) -> list[list[float]]:
    """段ごとの区切りの傾きを、左から右の並びに直す。区切りの傾きは基本枠の座標なので値は変えない。"""
    out = []
    for i, row in enumerate(page.rows):
        ks = list(page.cut_slants[i]) if page.cut_slants is not None else [0.0] * (len(row) - 1)
        out.append(ks[::-1] if direction == "right_to_left" else ks)
    return out


def _value(e: Expression | float) -> float:
    return e if isinstance(e, float) else e.value()


def _bleed_polygon(lt: float, kl: float, rt: float, kr: float, t: float, b: float, first: bool, last: bool,
                   spec: PageSpec, side: PageSide) -> tuple[list[tuple[float, float]], bool]:
    """断ち切りのコマを、基本枠の辺に接する辺だけ塗り足しまで伸ばす（ノドの辺は伸ばさない）。斜めの辺は線の向きのまま伸ばす。"""
    W, H = spec.frame_width_mm, spec.frame_height_mm
    ox, oy = spec.frame_origin_in_trim()
    moved = False
    y0, y1 = t, b
    if t <= _SOLVE_TOL:
        y0, moved = -oy - spec.bleed_mm, True
    if b >= H - _SOLVE_TOL:
        y1, moved = H + oy + spec.bleed_mm, True
    left = lambda y: lt + kl * (y - t)  # noqa: E731
    right = lambda y: rt + kr * (y - t)  # noqa: E731
    pts = [[left(y0), y0], [right(y0), y0], [right(y1), y1], [left(y1), y1]]
    # 左のページはノドが右、右のページはノドが左
    if first and lt <= _SOLVE_TOL and side == "左":
        pts[0][0] = pts[3][0] = -ox - spec.bleed_mm
        moved = True
    if last and rt >= W - _SOLVE_TOL and side == "右":
        pts[1][0] = pts[2][0] = W + ox + spec.bleed_mm
        moved = True
    return [(x, y) for x, y in pts], moved


def constrained_page_frames(page: NamePage, spec: PageSpec, direction: ReadingDirection, side: PageSide,
                            pinned: Mapping[int, PanelFrame], min_panel_mm: float) -> ConstrainedPageLayout:
    """1ページを解く。pinned は {コマの番号: 人が決めた枠}（このページのコマだけ）。min_panel_mm はコマの最小の幅と高さ（必須）。
    固定した枠は、崩れても出力では動かさない（人の枠を計算で書き換えない）。崩れたときは周りのコマが解いた位置になるので、
    重なりや隙間は検査（frame_shape_checks）でも出る。ページの全部のコマを固定したときは何も計算しない。"""
    if min_panel_mm <= 0:
        raise LayoutInputError("コマの最小の大きさは0より大きくなければならない")
    page_ns = {p.n for p in page.panels}
    stray = sorted(set(pinned) - page_ns)
    if stray:
        raise LayoutInputError(f"{page.page}ページ：固定する枠のコマ {stray} がこのページに無い")
    if page_ns and page_ns <= set(pinned):
        return ConstrainedPageLayout(frames={n: pinned[n] for n in sorted(page_ns)}, broken=[])
    hs_ratio, ws_ratio = validate_tier_input(page, spec)
    W, H = spec.frame_width_mm, spec.frame_height_mm
    gx, gy = spec.gutter_x_mm, spec.gutter_y_mm
    slants = _visual_slants(page, direction)
    s = Solver()

    def add(c, what: str) -> None:
        if isinstance(c, bool):
            # 両辺が定数のとき（1段に1コマで幅が基本枠の幅に決まる等）は、比べた結果がそのまま来る
            if not c:
                raise LayoutConflictError(f"{page.page}ページ：必須の制約が両立しない（{what}）")
            return
        try:
            s.addConstraint(c)
        except UnsatisfiableConstraint as e:
            raise LayoutConflictError(f"{page.page}ページ：必須の制約が両立しない（{what}）") from e

    nrows = len(page.rows)
    t = [Variable(f"t{i}") for i in range(nrows)]
    b = [Variable(f"b{i}") for i in range(nrows)]
    h = [b[i] - t[i] for i in range(nrows)]
    hs = Variable("hs")
    add(t[0] == 0, "基本枠の上の辺")
    add(b[-1] == H, "基本枠の下の辺")
    for i in range(nrows):
        add(h[i] >= min_panel_mm, f"{i + 1}段目の最小の高さ")
        if i + 1 < nrows:
            add(t[i + 1] == b[i] + gy, f"{i + 1}段目と{i + 2}段目の隙間")

    pinned_rows = {i for i, row in enumerate(page.rows) if any(n in pinned for n in row)}
    cells: list[_Cell] = []
    ws_vars: list[Variable] = []
    for i, row in enumerate(page.rows):
        ratios = dict(zip(row, ws_ratio[i], strict=False))
        visual = row[::-1] if direction == "right_to_left" else list(row)
        ks = slants[i]
        ws = Variable(f"ws{i}")
        ws_vars.append(ws)
        # 区切りごとに、左のコマの右の辺（上端の x）を変数にする。右のコマの左の辺は、傾きに沿った隙間だけ右
        xl = [Variable(f"xl{i}_{c}") for c in range(len(visual) - 1)]
        xr = [xl[c] + gx * math.sqrt(1 + ks[c] ** 2) for c in range(len(visual) - 1)]
        for v, n in enumerate(visual):
            first, last = v == 0, v == len(visual) - 1
            cell = _Cell(n=n, row=i, ratio=ratios[n],
                         left_top=0.0 if first else xr[v - 1], left_k=0.0 if first else ks[v - 1],
                         right_top=W if last else xl[v], right_k=0.0 if last else ks[v])
            w_top = cell.right_top - cell.left_top
            w_bot = w_top + (cell.right_k - cell.left_k) * h[i]
            add(w_top >= min_panel_mm, f"コマ{n}の上端の最小の幅")
            add(w_bot >= min_panel_mm, f"コマ{n}の下端の最小の幅")
            if n not in pinned:
                # 斜めのコマの幅は高さの真ん中で測る（面積÷高さ。線形のまま書ける）
                mean_w = w_top + (cell.right_k - cell.left_k) * h[i] / 2
                add((mean_w == ws * cell.ratio) | strength.medium, f"コマ{n}の幅の比")
            cells.append(cell)
        if i not in pinned_rows:
            add((h[i] == hs * hs_ratio[i]) | strength.medium, f"{i + 1}段目の高さの比")

    # 人が固定した枠（強）。外接する四角の4辺を合わせる。斜めの辺の外側の x は傾きの符号で決まるので線形のまま書ける
    for c in cells:
        if c.n not in pinned:
            continue
        x0, y0, x1, y1 = _clip_to_frame(polygon_bbox(pinned[c.n].polygon_mm), spec)
        left_out = c.left_top + min(0.0, c.left_k) * h[c.row]
        right_out = c.right_top + max(0.0, c.right_k) * h[c.row]
        for expr, val in ((t[c.row], y0), (b[c.row], y1), (left_out, x0), (right_out, x1)):
            add((expr == val) | strength.strong, f"コマ{c.n}の固定した枠")
    s.updateVariables()

    frames: dict[int, PanelFrame] = {}
    broken: list[BrokenConstraint] = []
    hs_v = hs.value()
    for c in cells:
        tv, bv = t[c.row].value(), b[c.row].value()
        hv = bv - tv
        lt, rt = _value(c.left_top), _value(c.right_top)
        poly = [(lt, tv), (rt, tv), (rt + c.right_k * hv, bv), (lt + c.left_k * hv, bv)]
        if c.n in pinned:
            want = _clip_to_frame(polygon_bbox(pinned[c.n].polygon_mm), spec)
            got = polygon_bbox(poly)
            if any(abs(a - g) > _SOLVE_TOL for a, g in zip(want, got, strict=False)):
                broken.append(BrokenConstraint(page=page.page, panel=c.n, kind="固定した枠", wanted=_fmt(want), got=_fmt(got)))
            frames[c.n] = pinned[c.n]
            continue
        if c.row not in pinned_rows and abs(hv - hs_v * hs_ratio[c.row]) > _SOLVE_TOL:
            broken.append(BrokenConstraint(page=page.page, panel=c.n, kind="高さの比",
                                           wanted=f"{hs_ratio[c.row]}", got=f"高さ {round(hv, 3)}（比の1あたり {round(hs_v, 3)}）"))
        mean_w = (rt - lt) + (c.right_k - c.left_k) * hv / 2
        ws_v = ws_vars[c.row].value()
        if abs(mean_w - ws_v * c.ratio) > _SOLVE_TOL:
            broken.append(BrokenConstraint(page=page.page, panel=c.n, kind="幅の比",
                                           wanted=f"{c.ratio}", got=f"幅 {round(mean_w, 3)}（比の1あたり {round(ws_v, 3)}）"))
        shape = next(p.shape for p in page.panels if p.n == c.n)
        moved = False
        if shape == "断ち切り":
            row_visual = [x for x in cells if x.row == c.row]
            poly, moved = _bleed_polygon(lt, c.left_k, rt, c.right_k, tv, bv, c is row_visual[0], c is row_visual[-1], spec, side)
        frames[c.n] = PanelFrame(polygon_mm=poly, bleeds=moved)
    return ConstrainedPageLayout(frames=frames, broken=broken)


def constrained_layout_draft(draft: NameDraft, pinned: Mapping[int, PanelFrame],
                             min_panel_mm: float) -> tuple[NameDraft, list[BrokenConstraint]]:
    """全ページを解き、枠を入れた写しと、指定どおりにならなかったコマの一覧を返す（元の draft は変えない）。
    pinned は {コマの番号: 人が決めた枠}。呼ぶ側が、行の human_hand_fields に 'frame' があるコマの枠を渡す。"""
    known = {p.n for p in draft.all_panels()}
    stray = sorted(set(pinned) - known)
    if stray:
        raise LayoutInputError(f"固定する枠のコマ {stray} がネームに無い")
    pages = []
    broken: list[BrokenConstraint] = []
    for page, side in zip(draft.pages, page_sides(draft), strict=False):
        here = {n: f for n, f in pinned.items() if n in {p.n for p in page.panels}}
        res = constrained_page_frames(page, draft.page_spec, draft.reading_direction, side, here, min_panel_mm)
        broken += res.broken
        panels = [p.model_copy(update={"frame": res.frames[p.n]}) for p in page.panels]
        pages.append(page.model_copy(update={"panels": panels}))
    return draft.model_copy(update={"pages": pages}), broken
