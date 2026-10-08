"""1ページを層ごとの絵にする（書き出しの PNG・PDF・PSD で同じ物を使う）。

層の順（下から。V3細部の決めごと 10.3）：
  紙 → コマごとの絵のグループ（地の色・コマの1枚の絵・層） → トーン・図形 → コマ枠 → 人の手 → フキダシ → 写植 → 描き文字 → ノンブル
見開き（render_spread）は：紙 → 見開きの絵 → 左のページの層（紙を除く。ノドで切る） → 右のページの層（同じ）
どの層の名前も「名前 [id]」で終わる。id は正本の行の id か、ページ・コマの id に「-paper」などを付けたもの
（PSD を戻すとき、この印で層と行を結び付ける。print_export/psd_import_matching.py）。

座標：正本は基本枠の mm（x は右、y は下）。絵は塗り足しを含むページの画素（dpi）。見開きでは、右のページは仕上がりの幅だけ右に置く。
フキダシのしっぽと、つなげたフキダシ（joined_to_previous）は、外形と多角形の和（shapely）で1つの形にして描く（重なった所に線を残さない）。
足りない値（書体・文字の大きさ・枠の線・置き場の決まっていない絵）は、補わずに止める（RenderRefused）。
"""

import io
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter
from shapely.geometry import LineString, MultiPolygon, Point, Polygon

from v3server.name_structure.image_placement import ImagePlacement
from v3server.name_structure.item_styles import (
    BalloonShape,
    FrameStyle,
    ShapeSpec,
    ToneSpec,
    blend_mode_of,
)
from v3server.name_structure.item_transform import ItemTransform, transform_matrix
from v3server.name_structure.print_settings import Typesetting
from v3server.name_structure.reading_direction import PageSpec
from v3server.print_export.binarize_and_halftone import halftone_screen
from v3server.print_export.book_layout import NombrePlace
from v3server.print_export.print_pdf_export import canvas_size_px
from v3server.print_export.text_render import RenderedText

MM_PER_INCH = 25.4

LAYER_NAME_PAPER = "紙"
LAYER_NAME_PANEL = "コマ"
LAYER_NAME_PANEL_FILL = "コマの地"
LAYER_NAME_PANEL_IMAGE = "コマの絵"
LAYER_NAME_ITEMS = "トーン・図形"
LAYER_NAME_PANEL_FRAME = "コマ枠"
LAYER_NAME_HAND_DRAWN = "人の手"
LAYER_NAME_BALLOON = "フキダシ"
LAYER_NAME_TYPESET = "写植"
LAYER_NAME_SFX = "描き文字"
LAYER_NAME_NOMBRE = "ノンブル"
LAYER_NAME_SPREAD_IMAGE = "見開きの絵"
LAYER_NAME_PAGE = "ページ"

# ノンブルは1行の数字なので、組版は決まった形で組む（行間・改行・縦中横は使わない）
NOMBRE_TYPESETTING = {"line_spacing_ratio": 0, "line_break": "none", "tate_chu_yoko_max_digits": 0,
                      "tate_chu_yoko_marks": False, "align": "start"}

# しっぽの曲がりを折れ線にするときの分け数（見た目の決まりではなく、曲線を多角形にする細かさ）
TAIL_CURVE_STEPS = 16

# 合成のときに作る印（ページ・コマの id に付ける）
SYNTHETIC_SUFFIXES = ("-paper", "-fill", "-image", "-items", "-frame", "-hand", "-balloons", "-typeset", "-sfx",
                      "-balloon", "-nombre")


class RenderRefused(ValueError):
    """書き出しに要る値が無い（補わない）。"""


def layer_name(name: str, marker: str) -> str:
    return f"{name} [{marker}]"


@dataclass
class Node:
    """層かグループ。image は RGBA で、left・top がページの画素の置き場。"""

    name: str
    marker: str
    image: Image.Image | None = None
    left: int = 0
    top: int = 0
    blend: str = "normal"
    opacity: float = 1.0
    hidden: bool = False
    children: list["Node"] | None = None
    # 写植・描き文字の文字の情報（PSD の文字層）
    text: dict[str, Any] | None = None
    # 正本の表（PSD を戻すとき、どの表の行か）
    table: str | None = None

    @property
    def full_name(self) -> str:
        return layer_name(self.name, self.marker)


@dataclass
class PageContent:
    """1ページを描くのに要る正本の値（http_routes/export_routes.py の読み込みで作る）。"""

    page_id: str
    spec: PageSpec
    text_direction: str
    preferences: dict[str, Any]
    panels: list[Any]
    layers: list[Any]
    texts: list[Any]
    page_items: list[Any]
    images: dict[str, Any] = field(default_factory=dict)
    # ノンブル（book_layout.py が決める）。出さないページは None
    nombre: NombrePlace | None = None


@dataclass
class RenderedPage:
    width: int
    height: int
    nodes: list[Node]
    composite: Image.Image


# ---------------------------------------------------------------- 座標


def mm_to_px_matrix(spec: PageSpec, dpi: float, offset_x_mm: float = 0.0) -> np.ndarray:
    """基本枠の mm → 絵の画素。offset_x_mm は、見開きの絵の中でこのページを右へずらす幅（右のページは仕上がりの幅）。"""
    ox, oy = spec.frame_origin_in_trim()
    k = dpi / MM_PER_INCH
    return np.array([[k, 0, (ox + spec.bleed_mm + offset_x_mm) * k], [0, k, (oy + spec.bleed_mm) * k], [0, 0, 1]], float)


@dataclass
class PageCanvas:
    """ページを描く絵の大きさと、その中のページの置き場（見開きでは右のページを仕上がりの幅だけ右へ）。"""

    size_px: tuple[int, int]
    offset_x_mm: float


def single_page_canvas(spec: PageSpec, dpi: float) -> PageCanvas:
    return PageCanvas(canvas_size_px(spec, dpi), 0.0)


def spread_size_px(spec: PageSpec, dpi: float) -> tuple[int, int]:
    """見開き（2ページの仕上がり＋外側の塗り足し）の画素数。"""
    return (round((2 * spec.trim_width_mm + 2 * spec.bleed_mm) / MM_PER_INCH * dpi),
            round((spec.trim_height_mm + 2 * spec.bleed_mm) / MM_PER_INCH * dpi))


def gutter_x_px(spec: PageSpec, dpi: float) -> int:
    """見開きの絵の中のノドの位置（画素）。"""
    return round((spec.bleed_mm + spec.trim_width_mm) / MM_PER_INCH * dpi)


def _pts(m: np.ndarray, points) -> list[tuple[float, float]]:
    out = []
    for x, y in points:
        v = m @ np.array([x, y, 1.0])
        out.append((float(v[0]), float(v[1])))
    return out


def warp(img: Image.Image, m: np.ndarray, size: tuple[int, int]) -> tuple[Image.Image, int, int] | None:
    """絵の画素 → ページの画素の行列 m で移し、はみ出しを切った (絵, left, top)。ページに入らなければ None。"""
    w, h = img.size
    corners = _pts(m, [(0, 0), (w, 0), (w, h), (0, h)])
    x0 = max(0, math.floor(min(p[0] for p in corners)))
    y0 = max(0, math.floor(min(p[1] for p in corners)))
    x1 = min(size[0], math.ceil(max(p[0] for p in corners)))
    y1 = min(size[1], math.ceil(max(p[1] for p in corners)))
    if x1 <= x0 or y1 <= y0:
        return None
    shift = np.array([[1, 0, x0], [0, 1, y0], [0, 0, 1]], float)
    inv = np.linalg.inv(m) @ shift
    out = img.convert("RGBA").transform((x1 - x0, y1 - y0), Image.Transform.AFFINE,
                                        tuple(inv[:2].flatten()), resample=Image.Resampling.BICUBIC)
    return out, x0, y0


def _poly_mask(size: tuple[int, int], polys: list[list[tuple[float, float]]], left: int = 0, top: int = 0) -> Image.Image:
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    for p in polys:
        d.polygon([(x - left, y - top) for x, y in p], fill=255)
    return m


def _clip(node_img: Image.Image, left: int, top: int, polys) -> Image.Image:
    a = node_img.getchannel("A")
    mask = _poly_mask(node_img.size, polys, left, top)
    node_img = node_img.copy()
    node_img.putalpha(ImageChops.multiply(a, mask))
    return node_img


# ---------------------------------------------------------------- 仕上げ


def apply_adjustments(img: Image.Image, adjustments: list[dict], dpi: float) -> Image.Image:
    """白黒・明るさ・ぼかしを順に当てる（重ね方は層の合成で当てる）。"""
    img = img.convert("RGBA")
    for a in adjustments:
        alpha = img.getchannel("A")
        if a["kind"] == "monochrome":
            g = img.convert("L")
            if a.get("threshold") is not None:
                t = a["threshold"]
                g = g.point(lambda v, t=t: 255 if v >= t else 0)
            img = Image.merge("RGBA", (g, g, g, alpha))
        elif a["kind"] == "brightness":
            d = round(a["amount"] * 255)
            rgb = img.convert("RGB").point(lambda v, d=d: max(0, min(255, v + d)))
            img = Image.merge("RGBA", (*rgb.split(), alpha))
        elif a["kind"] == "blur":
            img = img.filter(ImageFilter.GaussianBlur(a["radius_mm"] / MM_PER_INCH * dpi))
    return img


def _blend(base: np.ndarray, top: np.ndarray, mode: str) -> np.ndarray:
    if mode == "normal":
        return top
    if mode == "multiply":
        return base * top
    if mode == "screen":
        return 1 - (1 - base) * (1 - top)
    if mode == "darken":
        return np.minimum(base, top)
    if mode == "lighten":
        return np.maximum(base, top)
    if mode == "overlay":
        return np.where(base < 0.5, 2 * base * top, 1 - 2 * (1 - base) * (1 - top))
    raise RenderRefused(f"知らない重ね方: {mode}")


def composite(nodes: list[Node], size: tuple[int, int]) -> Image.Image:
    """層を下から重ねた RGB の絵。グループの中も同じ重ね方で、グループは通過（pass through）として扱う。"""
    acc = np.ones((size[1], size[0], 3), float)

    def paint(ns: list[Node]):
        nonlocal acc
        for n in ns:
            if n.hidden:
                continue
            if n.children is not None:
                paint(n.children)
                continue
            if n.image is None:
                continue
            arr = np.asarray(n.image.convert("RGBA"), float) / 255
            h, w = arr.shape[:2]
            region = acc[n.top:n.top + h, n.left:n.left + w]
            a = arr[..., 3:4] * n.opacity
            mixed = _blend(region, arr[..., :3], n.blend)
            acc[n.top:n.top + h, n.left:n.left + w] = region * (1 - a) + mixed * a

    paint(nodes)
    return Image.fromarray(np.clip(acc * 255 + 0.5, 0, 255).astype(np.uint8), "RGB")


# ---------------------------------------------------------------- トーン・図形


def _tone_alpha(spec: ToneSpec, box_px: tuple[int, int, int, int], dpi: float, center_px) -> Image.Image:
    """箱の大きさの L の絵（255 が色の付く所）。"""
    w, h = box_px[2] - box_px[0], box_px[3] - box_px[1]
    k = spec.kind
    if k in ("dots", "lines"):
        gray = np.full((h, w), round(255 * (1 - spec.density)), np.uint8)
        black = halftone_screen(gray, dpi, spec.lines_per_inch, spec.angle_deg, "round" if k == "dots" else "line",
                                origin_px=(box_px[0], box_px[1]))
        return Image.fromarray(black.astype(np.uint8) * 255, "L")
    if k == "gradient":
        # 濃さを density から density_end へ、angle_deg の向きに変え、網点にする（網の目はページで揃える）
        a = math.radians(spec.angle_deg)
        ys, xs = np.mgrid[0:h, 0:w]
        t = (xs * math.cos(a) + ys * math.sin(a))
        t = (t - t.min()) / max(1e-9, t.max() - t.min())
        dens = spec.density + (spec.density_end - spec.density) * t
        gray = np.clip(np.round(255 * (1 - dens)), 0, 255).astype(np.uint8)
        black = halftone_screen(gray, dpi, spec.lines_per_inch, spec.screen_angle_deg, spec.dot_shape,
                                origin_px=(box_px[0], box_px[1]))
        return Image.fromarray(black.astype(np.uint8) * 255, "L")
    rng = np.random.default_rng(spec.seed)
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    if k in ("sand", "snow"):
        r = max(0.5, spec.grain_mm / MM_PER_INCH * dpi / 2)
        n = int(spec.density * w * h / max(1.0, (2 * r) ** 2))
        for x, y in zip(rng.uniform(0, w, n), rng.uniform(0, h, n), strict=False):
            d.ellipse((x - r, y - r, x + r, y + r), fill=255)
        return m
    if k == "focus_lines":
        cx, cy = center_px[0] - box_px[0], center_px[1] - box_px[1]
        outer = math.hypot(max(cx, w - cx), max(cy, h - cy))
        inner = outer * spec.inner_ratio
        width = max(1.0, spec.density * 2 * math.pi * outer / spec.line_count)
        for ang in rng.uniform(0, 2 * math.pi, spec.line_count):
            start = inner * rng.uniform(1.0, 1.3)
            sx, sy = cx + start * math.cos(ang), cy + start * math.sin(ang)
            ex, ey = cx + outer * math.cos(ang), cy + outer * math.sin(ang)
            nx, ny = -math.sin(ang), math.cos(ang)
            d.polygon([(sx, sy), (ex + nx * width / 2, ey + ny * width / 2), (ex - nx * width / 2, ey - ny * width / 2)],
                      fill=255)
        return m
    if k == "speed_lines":
        a = math.radians(spec.angle_deg)
        ux, uy = math.cos(a), math.sin(a)
        nx, ny = -uy, ux
        span = math.hypot(w, h)
        width = max(1.0, spec.density * span / spec.line_count)
        for off, length, pos in zip(rng.uniform(-span / 2, span / 2, spec.line_count),
                                    rng.uniform(0.3, 1.0, spec.line_count), rng.uniform(-0.5, 0.5, spec.line_count), strict=False):
            cx, cy = w / 2 + nx * off + ux * pos * span, h / 2 + ny * off + uy * pos * span
            hl = length * span / 2
            d.polygon([(cx - ux * hl, cy - uy * hl), (cx + ux * hl + nx * width / 2, cy + uy * hl + ny * width / 2),
                       (cx + ux * hl - nx * width / 2, cy + uy * hl - ny * width / 2)], fill=255)
        return m
    raise RenderRefused(f"知らないトーン: {k}")


def _hex(c: str, alpha: float = 1.0) -> tuple[int, int, int, int]:
    return (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16), round(alpha * 255))


def _shape_image(spec: ShapeSpec, box_mm, k: float) -> Image.Image:
    """箱の大きさ（画素）の RGBA に図形を描く。点は箱の左上からの mm を画素にして描く。"""
    w, h = max(1, round((box_mm[2] - box_mm[0]) * k)), max(1, round((box_mm[3] - box_mm[1]) * k))
    pad = round((spec.stroke.width_mm * k) if spec.stroke else 0) + 2
    if spec.shadow:
        pad += round((abs(spec.shadow.dx_mm) + abs(spec.shadow.dy_mm) + 3 * spec.shadow.blur_mm) * k)
    size = (w + 2 * pad, h + 2 * pad)

    def outline():
        if spec.kind in ("rect", "ellipse"):
            return None
        return [((x - box_mm[0]) * k + pad, (y - box_mm[1]) * k + pad) for x, y in spec.points_mm]

    def draw(img, color_fill, color_line, dx=0.0, dy=0.0):
        d = ImageDraw.Draw(img)
        lw = round(spec.stroke.width_mm * k) if spec.stroke else 0
        box = (pad + dx, pad + dy, pad + w + dx, pad + h + dy)
        pts = outline()
        if pts is not None:
            pts = [(x + dx, y + dy) for x, y in pts]
        if spec.kind == "rect":
            d.rectangle(box, fill=color_fill, outline=color_line, width=lw)
        elif spec.kind == "ellipse":
            d.ellipse(box, fill=color_fill, outline=color_line, width=lw)
        elif spec.kind == "path":
            d.line(pts, fill=color_line or color_fill, width=max(1, lw), joint="curve")
        else:
            d.polygon(pts, fill=color_fill, outline=color_line, width=lw)

    out = Image.new("RGBA", size, (0, 0, 0, 0))
    if spec.shadow:
        s = spec.shadow
        sh = Image.new("RGBA", size, (0, 0, 0, 0))
        c = _hex(s.color, s.opacity)
        draw(sh, c if spec.fill else None, c if spec.stroke else None, s.dx_mm * k, s.dy_mm * k)
        if s.blur_mm:
            sh = sh.filter(ImageFilter.GaussianBlur(s.blur_mm * k))
        out = Image.alpha_composite(out, sh)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw(layer, _hex(spec.fill.color, spec.fill.opacity) if spec.fill else None,
         _hex(spec.stroke.color) if spec.stroke else None)
    return Image.alpha_composite(out, layer), pad


# ---------------------------------------------------------------- 本体


def _frame_polygon(panel) -> list[tuple[float, float]]:
    poly = (panel.frame or {}).get("polygon_mm")
    if not poly:
        raise RenderRefused(f"コマ {panel.id} に枠が無い")
    return [tuple(p) for p in poly]


def _frame_style(panel, prefs) -> FrameStyle:
    raw = panel.frame_style or prefs.get("frame_style")
    if raw is None:
        raise RenderRefused(f"コマ {panel.id} の枠の線が決まっていない（コマの frame_style か、作品の preferences.frame_style）")
    return FrameStyle.model_validate(raw)


def _placed_image(img: Image.Image, placement: dict, mm2px: np.ndarray, size, adjustments, dpi):
    pl = ImagePlacement.model_validate(placement)
    m = mm2px @ pl.image_px_to_page_mm()
    img = apply_adjustments(img, adjustments, dpi)
    got = warp(img, m, size)
    if got is None:
        return None
    out, left, top = got
    x0, y0, x1, y1 = pl.crop_px
    crop_quad = _pts(m, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    return _clip(out, left, top, [crop_quad]), left, top


def _unit(dx: float, dy: float) -> tuple[float, float]:
    n = math.hypot(dx, dy)
    return dx / n, dy / n


def tail_polygon(body: Polygon, tip: tuple[float, float], base_width: float, bend_ratio: float) -> Polygon | None:
    """フキダシの外形 body から tip へ伸びるしっぽの多角形（画素）。先が外形の中なら None（しっぽは見えない）。

    根元は、外形の中の点から先へ引いた線が外形を出る所。そこから幅の半分だけ内側に根元の辺を置くので、
    外形と重ねて和を取ると、根元に線が残らない。曲がりは、両側の辺を同じ向きに膨らませる（2次の曲線）。"""
    tip_pt = Point(tip)
    if body.contains(tip_pt):
        return None
    c = body.centroid if body.contains(body.centroid) else body.representative_point()
    crossing = LineString([c, tip_pt]).intersection(body.exterior)
    pts = [crossing] if crossing.geom_type == "Point" else list(getattr(crossing, "geoms", []))
    pts = [p for p in pts if p.geom_type == "Point"]
    if not pts:
        return None
    exit_pt = min(pts, key=lambda p: p.distance(tip_pt))
    dx, dy = _unit(tip[0] - c.x, tip[1] - c.y)
    nx, ny = -dy, dx
    bx, by = exit_pt.x - dx * base_width / 2, exit_pt.y - dy * base_width / 2
    length = math.hypot(tip[0] - bx, tip[1] - by)
    sides = []
    for sgn in (1, -1):
        sx, sy = bx + sgn * nx * base_width / 2, by + sgn * ny * base_width / 2
        cx = (sx + tip[0]) / 2 + nx * bend_ratio * length
        cy = (sy + tip[1]) / 2 + ny * bend_ratio * length
        curve = []
        for i in range(TAIL_CURVE_STEPS + 1):
            t = i / TAIL_CURVE_STEPS
            curve.append(((1 - t) ** 2 * sx + 2 * (1 - t) * t * cx + t * t * tip[0],
                          (1 - t) ** 2 * sy + 2 * (1 - t) * t * cy + t * t * tip[1]))
        sides.append(curve)
    ring = sides[0] + list(reversed(sides[1]))[1:]
    return Polygon(ring).buffer(0)


def balloon_geometry(t, bs: BalloonShape, mm2px: np.ndarray) -> Polygon:
    """フキダシ1つの形（画素）。しっぽの先（文字の tail_target_mm）があれば、しっぽを足した形。"""
    body = Polygon(_pts(mm2px, bs.outline_mm)).buffer(0)
    if t.tail_target_mm is None:
        return body
    if bs.tail_base_width_mm is None or bs.tail_bend_ratio is None:
        raise RenderRefused(f"フキダシ {t.id} のしっぽの根元の幅・曲がり（balloon_shape.tail_base_width_mm・tail_bend_ratio）"
                            "が決まっていない")
    k = mm2px[0, 0]
    tail = tail_polygon(body, _pts(mm2px, [t.tail_target_mm])[0], bs.tail_base_width_mm * k, bs.tail_bend_ratio)
    return body if tail is None else body.union(tail)


def _draw_shape(size, geom, fill, line, width) -> Image.Image:
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    polys = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
    for p in polys:
        d.polygon(list(p.exterior.coords), fill=fill, outline=line, width=width)
        for hole in p.interiors:
            d.polygon(list(hole.coords), fill=(0, 0, 0, 0), outline=line, width=width)
    return img


def text_fill(t) -> str:
    """文字の色（decoration.fill）。無ければ止める（色を補わない。取り込んだ文字・古い文字は無いことがある。
    書き出し前の確認も、この関数で同じ理由を出す）。"""
    fill = (t.decoration or {}).get("fill")
    if not fill:
        raise RenderRefused(f"文字「{t.text[:12]}」（{t.id}）の色（decoration.fill）が決まっていない。"
                            "取り込んだ文字か古い文字は色を持たないことがある。文字の飾りで色を選び直す")
    return fill


def _text_job(t, content: PageContent, dpi: float, font_path: Callable[[str], str]) -> dict:
    return text_job(t, content.preferences, content.text_direction, dpi, font_path)


def text_job(t, preferences: dict[str, Any] | None, text_direction: str, dpi: float,
             font_path: Callable[[str], str]) -> dict:
    """文字1つを render_text.js へ渡す形にする（書き出し・入稿前の確かめ・1つだけ組む口で同じ）。"""
    prefs = preferences or {}
    k = dpi / MM_PER_INCH
    if t.box_mm is None:
        raise RenderRefused(f"文字 {t.id} の箱（box_mm）が決まっていない")
    if t.font_size_pt is None:
        raise RenderRefused(f"文字 {t.id} の大きさ（font_size_pt）が決まっていない")
    family = t.font_family or prefs.get("fonts_by_kind", {}).get(t.item_kind)
    if family is None:
        raise RenderRefused(f"文字 {t.id} の書体が決まっていない（文字の font_family か、作品の preferences.fonts_by_kind）")
    raw_ts = t.typesetting or prefs.get("typesetting")
    if raw_ts is None:
        raise RenderRefused(f"文字 {t.id} の組版（行間・自動の改行・縦中横）が決まっていない（文字の typesetting か、作品の "
                            "preferences.typesetting）")
    b = t.box_mm
    deco = dict(t.decoration or {})
    deco["fill"] = text_fill(t)
    spans = []
    for sp in t.spans or []:
        spans.append({"start": sp["start"], "end": sp["end"], "size_ratio": sp.get("size_ratio"),
                      "embolden_ratio": sp.get("embolden_ratio"), "color": sp.get("color"),
                      "font_path": font_path(sp["font_family"]) if sp.get("font_family") else None})
    return {"id": t.id, "text": t.text, "font_path": font_path(family), "font_family": family,
            "font_size_px": t.font_size_pt / 72 * dpi,
            "vertical": (t.writing_direction or text_direction) == "vertical",
            "color": deco["fill"], "language": prefs.get("language"),
            "box_w_px": max(1, round((b[2] - b[0]) * k)), "box_h_px": max(1, round((b[3] - b[1]) * k)),
            "typesetting": Typesetting.model_validate(raw_ts).model_dump(), "spans": spans,
            "decoration": deco, "ruby": t.ruby or []}


def text_jobs(content: PageContent, dpi: float, font_path: Callable[[str], str]) -> list[dict]:
    """ページの文字（読む順）を、render_text.js に渡す形にする。入稿前の確かめも同じ形で組む。"""
    return [_text_job(t, content, dpi, font_path) for t in sorted(content.texts, key=lambda t: t.order)]


def nombre_job(content: PageContent, dpi: float, font_path: Callable[[str], str]) -> dict | None:
    nb = content.nombre
    if nb is None:
        return None
    return {"id": f"{content.page_id}-nombre", "text": nb.text, "font_path": font_path(nb.font_family),
            "font_size_px": nb.font_size_pt / 72 * dpi, "vertical": False, "color": nb.color,
            "language": (content.preferences or {}).get("language"), "box_w_px": 1, "box_h_px": 1,
            "typesetting": NOMBRE_TYPESETTING, "spans": [], "decoration": {"fill": nb.color}, "ruby": []}


def _nombre_node(content: PageContent, rt: RenderedText, dpi: float, offset_x_mm: float) -> Node:
    nb = content.nombre
    k = dpi / MM_PER_INCH
    bleed = content.spec.bleed_mm
    ax = (nb.x_mm + bleed + offset_x_mm) * k
    ay = (nb.y_mm + bleed) * k
    left = ax - {"left": 0, "center": rt.block_w / 2, "right": rt.block_w}[nb.anchor_x]
    top = ay - {"top": 0, "bottom": rt.block_h}[nb.anchor_y]
    img = rt.image
    return Node(LAYER_NAME_NOMBRE, f"{content.page_id}-nombre", img, round(left - (img.width - rt.block_w) / 2),
                round(top - (img.height - rt.block_h) / 2), table="pages")


def render_page(content: PageContent, dpi: float, load_image: Callable[[str], bytes],
                render_texts: Callable[[list[dict]], list[RenderedText]], font_path: Callable[[str], str],
                canvas: PageCanvas | None = None, with_paper: bool = True) -> RenderedPage:
    """1ページを層にする。canvas を渡すと、その大きさの絵の中にページを置く（見開き。render_spread が使う）。"""
    spec = content.spec
    canvas = canvas or single_page_canvas(spec, dpi)
    size = canvas.size_px
    k = dpi / MM_PER_INCH
    mm2px = mm_to_px_matrix(spec, dpi, canvas.offset_x_mm)
    pid = content.page_id
    prefs = content.preferences or {}
    nodes: list[Node] = []
    if with_paper:
        nodes.append(Node(LAYER_NAME_PAPER, f"{pid}-paper", Image.new("RGBA", size, (255, 255, 255, 255))))

    def open_image(image_id: str) -> Image.Image:
        return Image.open(io.BytesIO(load_image(image_id))).convert("RGBA")

    # コマごとの絵
    frames_px: dict[str, list[tuple[float, float]]] = {}
    hand: list[Node] = []
    panels = sorted(content.panels, key=lambda p: p.order)
    for panel in panels:
        poly_px = _pts(mm2px, _frame_polygon(panel))
        frames_px[panel.id] = poly_px
        style = _frame_style(panel, prefs)
        children: list[Node] = []
        if style.fill_color:
            fill = Image.new("RGBA", size, (0, 0, 0, 0))
            ImageDraw.Draw(fill).polygon(poly_px, fill=_hex(style.fill_color))
            children.append(Node(LAYER_NAME_PANEL_FILL, f"{panel.id}-fill", fill, table="panels"))
        if panel.image_id is not None:
            if panel.image_placement is None:
                raise RenderRefused(f"コマ {panel.id} の絵の置き場が決まっていない")
            got = _placed_image(open_image(panel.image_id), panel.image_placement, mm2px, size, panel.adjustments, dpi)
            if got:
                img, left, top = got
                children.append(Node(LAYER_NAME_PANEL_IMAGE, f"{panel.id}-image", _clip(img, left, top, [poly_px]),
                                     left, top, blend_mode_of(panel.adjustments), table="panels"))
        for la in sorted((x for x in content.layers if x.panel_id == panel.id), key=lambda x: x.stack_order):
            if la.image_id is None:
                continue
            if la.placement is None:
                raise RenderRefused(f"層 {la.id} の絵の置き場が決まっていない")
            got = _placed_image(open_image(la.image_id), la.placement, mm2px, size, la.adjustments, dpi)
            if not got:
                continue
            img, left, top = got
            node = Node(la.role, la.id, img if la.role == "human_hand" else _clip(img, left, top, [poly_px]),
                        left, top, blend_mode_of(la.adjustments), la.opacity, not la.visible, table="panel_layers")
            (hand if la.role == "human_hand" else children).append(node)
        nodes.append(Node(f"{LAYER_NAME_PANEL}{panel.order + 1}", panel.id, children=children, table="panels"))

    # トーン・図形
    items: list[Node] = []
    for it in sorted(content.page_items, key=lambda x: x.stack_order):
        box = it.box_mm
        if it.item_kind == "tone":
            ts = ToneSpec.model_validate(it.spec)
            target = ts.target
            if target.kind == "panel":
                if target.panel_id not in frames_px:
                    raise RenderRefused(f"トーン {it.id} を貼るコマ {target.panel_id} がこのページに無い")
                clip_polys = [frames_px[target.panel_id]]
            elif target.kind == "polygon":
                clip_polys = [_pts(mm2px, target.polygon_mm)]
            else:
                clip_polys = None
            (p0x, p0y), (p1x, p1y) = _pts(mm2px, [(box[0], box[1]), (box[2], box[3])])
            bx = [round(p0x), round(p0y), round(p1x), round(p1y)]
            center = _pts(mm2px, [ts.center_mm])[0] if ts.center_mm else None
            alpha = _tone_alpha(ts, tuple(bx), dpi, center)
            if target.kind == "mask":
                mask = open_image(target.image_id).convert("L").resize(alpha.size)
                alpha = ImageChops.multiply(alpha, mask)
            local = Image.new("RGBA", alpha.size, _hex(ts.color))
            local.putalpha(alpha)
            local_to_px = np.array([[1, 0, bx[0]], [0, 1, bx[1]], [0, 0, 1]], float)
            pad = 0
        else:
            ss = ShapeSpec.model_validate(it.spec)
            local, pad = _shape_image(ss, box, k)
            local_to_px = mm2px @ np.array([[1 / k, 0, box[0] - pad / k], [0, 1 / k, box[1] - pad / k], [0, 0, 1]])
            clip_polys = None
        t = ItemTransform.model_validate(it.transform or {})
        m = mm2px @ transform_matrix(t, box) @ np.linalg.inv(mm2px) @ local_to_px
        got = warp(apply_adjustments(local, it.adjustments, dpi), m, size)
        if not got:
            continue
        img, left, top = got
        if clip_polys:
            img = _clip(img, left, top, clip_polys)
        items.append(Node(it.item_kind, it.id, img, left, top, blend_mode_of(it.adjustments), it.opacity,
                          not it.visible, table="page_items"))
    nodes.append(Node(LAYER_NAME_ITEMS, f"{pid}-items", children=items))

    # コマ枠（コマの絵より上。V3細部の決めごと 10.3）
    frame = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(frame)
    for panel in panels:
        style = _frame_style(panel, prefs)
        if style.line_width_mm > 0:
            d.polygon(frames_px[panel.id], outline=_hex(style.line_color), width=max(1, round(style.line_width_mm * k)))
    nodes.append(Node(LAYER_NAME_PANEL_FRAME, f"{pid}-frame", frame, table="pages"))
    nodes.append(Node(LAYER_NAME_HAND_DRAWN, f"{pid}-hand", children=hand))

    # フキダシ（しっぽと、つなげたフキダシを1つの形にする）
    texts = sorted(content.texts, key=lambda t: t.order)
    groups: list[dict[str, Any]] = []
    last_in_panel: dict[str, int] = {}
    for t in texts:
        if not t.balloon_shape:
            continue
        bs = BalloonShape.model_validate(t.balloon_shape)
        if bs.kind == "none":
            continue
        if bs.line_width_mm is None or bs.line_color is None:
            raise RenderRefused(f"フキダシ {t.id} の線（line_width_mm・line_color）が決まっていない")
        geom = balloon_geometry(t, bs, mm2px)
        if t.joined_to_previous and t.panel_id in last_in_panel:
            g = groups[last_in_panel[t.panel_id]]
            g["geom"] = g["geom"].union(geom)
            g["joined"].append(t.id)
        else:
            last_in_panel[t.panel_id] = len(groups)
            groups.append({"id": t.id, "shape": bs, "geom": geom, "joined": []})
    balloons: list[Node] = []
    for g in groups:
        bs = g["shape"]
        bimg = _draw_shape(size, g["geom"], _hex(bs.fill_color) if bs.fill_color else None, _hex(bs.line_color),
                           max(1, round(bs.line_width_mm * k)))
        bbox = bimg.getbbox()
        if bbox:
            balloons.append(Node(LAYER_NAME_BALLOON, f"{g['id']}-balloon", bimg.crop(bbox), bbox[0], bbox[1],
                                 table="text_items"))

    # 写植・描き文字・ノンブル
    typeset: list[Node] = []
    sfx: list[Node] = []
    jobs = text_jobs(content, dpi, font_path)
    nb_job = nombre_job(content, dpi, font_path)
    all_jobs = jobs + ([nb_job] if nb_job else [])
    rendered = render_texts(all_jobs) if all_jobs else []
    for t, job, rt in zip(texts, jobs, rendered, strict=False):
        img = rt.image
        b = t.box_mm
        tr = ItemTransform.model_validate(t.transform or {})
        # 描いた絵の真ん中を箱の真ん中に合わせる
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        local = np.array([[1 / k, 0, cx - img.width / (2 * k)], [0, 1 / k, cy - img.height / (2 * k)], [0, 0, 1]])
        m = mm2px @ transform_matrix(tr, b) @ local
        got = warp(apply_adjustments(img, t.adjustments or [], dpi), m, size)
        if not got:
            continue
        timg, left, top = got
        info = {"text": t.text, "orientation": "vertical" if job["vertical"] else "horizontal",
                "font_name": job["font_family"], "font_size": job["font_size_px"],
                "color_rgb": list(_hex(job["color"])[:3]), "x": float(left), "y": float(top)}
        node = Node(t.speaker or t.item_kind, t.id, timg, left, top, blend_mode_of(t.adjustments or []), t.opacity,
                    text=info, table="text_items")
        (sfx if t.item_kind == "drawn_sfx" else typeset).append(node)
    nodes.append(Node(LAYER_NAME_BALLOON, f"{pid}-balloons", children=balloons))
    nodes.append(Node(LAYER_NAME_TYPESET, f"{pid}-typeset", children=typeset))
    nodes.append(Node(LAYER_NAME_SFX, f"{pid}-sfx", children=sfx))
    if nb_job:
        nodes.append(_nombre_node(content, rendered[-1], dpi, canvas.offset_x_mm))
    return RenderedPage(size[0], size[1], nodes, composite(nodes, size))


def _crop_nodes_x(nodes: list[Node], x0: int, x1: int) -> list[Node]:
    """層の絵を x0 ≤ x < x1 の範囲に切る（見開きで、ページの層をノドで切る）。範囲に入らない層は除く。"""
    out = []
    for n in nodes:
        if n.children is not None:
            out.append(Node(n.name, n.marker, None, n.left, n.top, n.blend, n.opacity, n.hidden,
                            _crop_nodes_x(n.children, x0, x1), n.text, n.table))
            continue
        if n.image is None:
            out.append(n)
            continue
        a, b = max(x0, n.left), min(x1, n.left + n.image.width)
        if b <= a:
            continue
        img = n.image.crop((a - n.left, 0, b - n.left, n.image.height))
        out.append(Node(n.name, n.marker, img, a, n.top, n.blend, n.opacity, n.hidden, None, n.text, n.table))
    return out


@dataclass
class SpreadContent:
    """見開き1つ。left・right は左右のページ（どちらが前のページかは book_layout.py が読む向きで決める）。"""

    spread_id: str
    left: PageContent
    right: PageContent
    image_id: str | None
    image_placement: dict | None
    adjustments: list
    # 見開きの絵の id → sha256（PageContent.images と同じ）
    images: dict[str, str]


def render_spread(content: SpreadContent, dpi: float, load_image: Callable[[str], bytes],
                  render_texts: Callable[[list[dict]], list[RenderedText]], font_path: Callable[[str], str]
                  ) -> RenderedPage:
    """見開きを1枚の絵にする。左右のページの層はノドで切り（ページの塗り足しが相手のページに出ないように）、
    ノドをまたぐ絵は見開きの絵（Spread の image）だけにする。"""
    spec = content.left.spec
    size = spread_size_px(spec, dpi)
    gx = gutter_x_px(spec, dpi)
    nodes: list[Node] = [Node(LAYER_NAME_PAPER, f"{content.spread_id}-paper",
                              Image.new("RGBA", size, (255, 255, 255, 255)))]
    if content.image_id is not None:
        if content.image_placement is None:
            raise RenderRefused(f"見開き {content.spread_id} の絵の置き場が決まっていない")
        img = Image.open(io.BytesIO(load_image(content.image_id))).convert("RGBA")
        got = _placed_image(img, content.image_placement, mm_to_px_matrix(spec, dpi, 0.0), size, content.adjustments,
                            dpi)
        if got:
            im, left, top = got
            nodes.append(Node(LAYER_NAME_SPREAD_IMAGE, f"{content.spread_id}-image", im, left, top,
                              blend_mode_of(content.adjustments), table="spreads"))
    for page, offset, (x0, x1) in ((content.left, 0.0, (0, gx)), (content.right, spec.trim_width_mm, (gx, size[0]))):
        r = render_page(page, dpi, load_image, render_texts, font_path, PageCanvas(size, offset), with_paper=False)
        nodes.append(Node(LAYER_NAME_PAGE, page.page_id, children=_crop_nodes_x(r.nodes, x0, x1), table="pages"))
    return RenderedPage(size[0], size[1], nodes, composite(nodes, size))


def split_spread(img: Image.Image, spec: PageSpec, dpi: float) -> tuple[Image.Image, Image.Image]:
    """見開きの絵をノドで左右の2ページに分ける。どちらのページも、ノドの側にも塗り足しの幅だけ相手の絵を残す
    （1ページの絵と同じ大きさ。print_pdf_export.canvas_size_px）。"""
    w, h = canvas_size_px(spec, dpi)
    if img.height != h:
        raise RenderRefused(f"見開きの高さ {img.height} がページの高さ {h} と違う")
    return img.crop((0, 0, w, h)), img.crop((img.width - w, 0, img.width, h))
