"""段と比からコマの座標を計算する（試作 p12 `rows_to_panels`、V3ハーネス設計 5.3）。
作業役は座標を出さず、段の高さの比と、段ごとのコマの幅の比だけを決める。座標はここで計算する。
計算で必ず守ること：
- 左右のコマの間（gutter_x）を上下の段の間（gutter_y）より狭くする。規格がそうなっていなければ計算しない。
- 段の横線は揃う（段ごとに全幅で割るので、作り方から揃う）。
- ノド側には断ち切りを伸ばさない。
縦線を段ごとにずらす・見開きの左右で横線をずらすは、比の決め方で決まるので、ここでは直さず検査（frame_shape_checks）で見つける。"""
from v3server.name_structure.name_draft_schema import NameDraft, NamePage, PanelFrame
from v3server.name_structure.reading_direction import PageSpec, ReadingDirection
from v3server.panel_layout.panel_geometry import FLOAT_EPS, Box, rect_polygon
from v3server.panel_layout.reading_direction_mirror import PageSide, page_sides


class LayoutInputError(ValueError):
    """段と比の入力が足りない・食い違っている。座標を推し量って埋めることはしない。"""


def validate_tier_input(page: NamePage, spec: PageSpec) -> tuple[list[float], list[list[float]]]:
    if page.spread:
        raise LayoutInputError(f"{page.page}ページ：見開きのページの割りは、まだ計算できない")
    if page.rows is None:
        raise LayoutInputError(f"{page.page}ページ：段の割り（rows）が決まっていない")
    undecided_shape = [p.n for p in page.panels if p.shape is None]
    if undecided_shape:
        # 断ち切りにするかは形で決まるので、未定のまま計算しない
        raise LayoutInputError(f"{page.page}ページ：形が未定のコマ {undecided_shape} がある")
    if page.row_height_ratios is None or page.cell_width_ratios is None:
        raise LayoutInputError(f"{page.page}ページ：段の高さの比かコマの幅の比が決まっていない")
    hs, ws = page.row_height_ratios, page.cell_width_ratios
    if len(hs) != len(page.rows) or len(ws) != len(page.rows):
        raise LayoutInputError(f"{page.page}ページ：段の数 {len(page.rows)} と比の数（高さ {len(hs)}・幅 {len(ws)}）が合わない")
    for i, (row, wr) in enumerate(zip(page.rows, ws)):
        if not row:
            raise LayoutInputError(f"{page.page}ページ：{i + 1}段目にコマが無い")
        if len(row) != len(wr):
            raise LayoutInputError(f"{page.page}ページ：{i + 1}段目のコマ {len(row)} と幅の比 {len(wr)} の数が合わない")
    if any(h <= 0 for h in hs) or any(w <= 0 for wr in ws for w in wr):
        raise LayoutInputError(f"{page.page}ページ：比に0以下がある")
    seq = [n for row in page.rows for n in row]
    if sorted(seq) != sorted(p.n for p in page.panels) or len(set(seq)) != len(seq):
        raise LayoutInputError(f"{page.page}ページ：段に並べたコマの番号と、ページのコマの番号が合わない")
    if page.cut_slants is not None:
        if len(page.cut_slants) != len(page.rows) or any(len(k) != len(r) - 1 for k, r in zip(page.cut_slants, page.rows)):
            raise LayoutInputError(f"{page.page}ページ：区切りの傾きの数が、段ごとの区切りの数（コマ数−1）と合わない")
    if spec.gutter_x_mm >= spec.gutter_y_mm:
        raise LayoutInputError("規格の左右の隙間が上下の隙間より狭くない")
    return hs, ws


def tier_boxes(page: NamePage, spec: PageSpec, direction: ReadingDirection) -> dict[int, Box]:
    """段と比から、各コマの四角（基本枠の座標・mm）を計算する。右から読む作品は段の中を右から、左から読む作品は左から並べる。"""
    hs, ws = validate_tier_input(page, spec)
    if page.cut_slants is not None and any(k != 0 for row in page.cut_slants for k in row):
        raise LayoutInputError(f"{page.page}ページ：斜めの区切りは constrained_tier_layout で計算する")
    W, H = spec.frame_width_mm, spec.frame_height_mm
    avail_h = H - spec.gutter_y_mm * (len(hs) - 1)
    out: dict[int, Box] = {}
    y = 0.0
    for row, h_ratio, w_ratios in zip(page.rows, hs, ws):
        h = avail_h * h_ratio / sum(hs)
        avail_w = W - spec.gutter_x_mm * (len(row) - 1)
        if direction == "right_to_left":
            x = W
            for n, wr in zip(row, w_ratios):
                w = avail_w * wr / sum(w_ratios)
                out[n] = (x - w, y, x, y + h)
                x -= w + spec.gutter_x_mm
        else:
            x = 0.0
            for n, wr in zip(row, w_ratios):
                w = avail_w * wr / sum(w_ratios)
                out[n] = (x, y, x + w, y + h)
                x += w + spec.gutter_x_mm
        y += h + spec.gutter_y_mm
    return out


def _bleed_box(box: Box, spec: PageSpec, side: PageSide) -> tuple[Box, bool]:
    """基本枠の辺に接している辺を、仕上がりの外の塗り足しまで伸ばす。ノドの辺は伸ばさない。
    伸ばせる辺が1つも無ければ、伸ばさずに返す（断ち切りの指定との食い違いは検査が見つける）。"""
    W, H = spec.frame_width_mm, spec.frame_height_mm
    ox, oy = spec.frame_origin_in_trim()
    x0, y0, x1, y1 = box
    moved = False
    if y0 <= FLOAT_EPS:
        y0, moved = -oy - spec.bleed_mm, True
    if y1 >= H - FLOAT_EPS:
        y1, moved = H + oy + spec.bleed_mm, True
    # 左のページはノドが右、右のページはノドが左
    if x0 <= FLOAT_EPS and side == "左":
        x0, moved = -ox - spec.bleed_mm, True
    if x1 >= W - FLOAT_EPS and side == "右":
        x1, moved = W + ox + spec.bleed_mm, True
    return (x0, y0, x1, y1), moved


def page_frames(page: NamePage, spec: PageSpec, direction: ReadingDirection, side: PageSide) -> dict[int, PanelFrame]:
    """1ページの各コマの枠。形が「断ち切り」のコマだけ、基本枠の外へ伸ばす。"""
    shapes = {p.n: p.shape for p in page.panels}
    frames: dict[int, PanelFrame] = {}
    for n, box in tier_boxes(page, spec, direction).items():
        if shapes[n] == "断ち切り":
            box, moved = _bleed_box(box, spec, side)
        else:
            moved = False
        frames[n] = PanelFrame(polygon_mm=rect_polygon(box), bleeds=moved)
    return frames


def layout_draft(draft: NameDraft) -> NameDraft:
    """全ページのコマに枠を入れた写しを返す（元の draft は変えない）。1ページでも比が足りなければ例外にする。"""
    sides = page_sides(draft)
    pages = []
    for page, side in zip(draft.pages, sides):
        frames = page_frames(page, draft.page_spec, draft.reading_direction, side)
        panels = [p.model_copy(update={"frame": frames[p.n]}) for p in page.panels]
        pages.append(page.model_copy(update={"panels": panels}))
    return draft.model_copy(update={"pages": pages})
