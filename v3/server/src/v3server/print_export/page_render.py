"""1ページを層ごとの絵にする（書き出しの PNG・PDF・PSD で同じ物を使う）。

層の順（下から。V3細部の決めごと 10.3）：
  紙 → コマごとの絵のグループ（地の色・コマの1枚の絵・層） → トーン・図形 → コマ枠 → 人の手 → フキダシ → 写植 → 描き文字
どの層の名前も「名前 [id]」で終わる。id は正本の行の id か、ページ・コマの id に「-paper」などを付けたもの
（PSD を戻すとき、この印で層と行を結び付ける。print_export/psd_import_matching.py）。

座標：正本は基本枠の mm（x は右、y は下）。絵は塗り足しを含むページの画素（dpi）。
足りない値（書体・文字の大きさ・枠の線・置き場の決まっていない絵）は、補わずに止める（RenderRefused）。
"""

import io
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from v3server.name_structure.image_placement import ImagePlacement
from v3server.name_structure.item_styles import (
    BalloonShape,
    FrameStyle,
    ShapeSpec,
    ToneSpec,
    blend_mode_of,
)
from v3server.name_structure.item_transform import ItemTransform, transform_matrix
from v3server.name_structure.reading_direction import PageSpec
from v3server.print_export.binarize_and_halftone import halftone_screen
from v3server.print_export.print_pdf_export import canvas_size_px

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

# 行と行の間（文字の大きさとの比）。今のアプリの縦書きの行間に合わせる値ではなく、書き出しの決めごと（未検証）
LINE_GAP_RATIO = 0.2

# 合成のときに作る印（ページ・コマの id に付ける）
SYNTHETIC_SUFFIXES = ("-paper", "-fill", "-image", "-items", "-frame", "-hand", "-balloons", "-typeset", "-sfx",
                      "-balloon")


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


@dataclass
class RenderedPage:
    width: int
    height: int
    nodes: list[Node]
    composite: Image.Image


# ---------------------------------------------------------------- 座標


def mm_to_px_matrix(spec: PageSpec, dpi: float) -> np.ndarray:
    ox, oy = spec.frame_origin_in_trim()
    k = dpi / MM_PER_INCH
    return np.array([[k, 0, (ox + spec.bleed_mm) * k], [0, k, (oy + spec.bleed_mm) * k], [0, 0, 1]], float)


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
        black = halftone_screen(gray, dpi, spec.lines_per_inch, spec.angle_deg, "round" if k == "dots" else "line")
        return Image.fromarray(black.astype(np.uint8) * 255, "L")
    if k == "gradient":
        a = math.radians(spec.angle_deg)
        ys, xs = np.mgrid[0:h, 0:w]
        t = (xs * math.cos(a) + ys * math.sin(a))
        t = (t - t.min()) / max(1e-9, t.max() - t.min())
        return Image.fromarray((spec.density * (1 - t) * 255).astype(np.uint8), "L")
    rng = np.random.default_rng(spec.seed)
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    if k in ("sand", "snow"):
        r = max(0.5, spec.grain_mm / MM_PER_INCH * dpi / 2)
        n = int(spec.density * w * h / max(1.0, (2 * r) ** 2))
        for x, y in zip(rng.uniform(0, w, n), rng.uniform(0, h, n)):
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
                                    rng.uniform(0.3, 1.0, spec.line_count), rng.uniform(-0.5, 0.5, spec.line_count)):
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


def render_page(content: PageContent, dpi: float, load_image: Callable[[str], bytes],
                render_texts: Callable[[list[dict]], list[Image.Image]], font_path: Callable[[str], str]
                ) -> RenderedPage:
    spec = content.spec
    size = canvas_size_px(spec, dpi)
    k = dpi / MM_PER_INCH
    mm2px = mm_to_px_matrix(spec, dpi)
    pid = content.page_id
    prefs = content.preferences or {}
    nodes: list[Node] = [Node(LAYER_NAME_PAPER, f"{pid}-paper", Image.new("RGBA", size, (255, 255, 255, 255)))]

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

    # フキダシと文字
    balloons: list[Node] = []
    typeset: list[Node] = []
    sfx: list[Node] = []
    texts = sorted(content.texts, key=lambda t: t.order)
    jobs = []
    for t in texts:
        if t.box_mm is None:
            raise RenderRefused(f"文字 {t.id} の箱（box_mm）が決まっていない")
        if t.font_size_pt is None:
            raise RenderRefused(f"文字 {t.id} の大きさ（font_size_pt）が決まっていない")
        family = t.font_family or prefs.get("fonts_by_kind", {}).get(t.item_kind)
        if family is None:
            raise RenderRefused(f"文字 {t.id} の書体が決まっていない（文字の font_family か、作品の preferences.fonts_by_kind）")
        b = t.box_mm
        deco = dict(t.decoration or {})
        if not deco.get("fill"):
            raise RenderRefused(f"文字 {t.id} の色（decoration.fill）が決まっていない")
        jobs.append({"id": t.id, "text": t.text, "font_path": font_path(family),
                     "font_size_px": t.font_size_pt / 72 * dpi,
                     "vertical": (t.writing_direction or content.text_direction) == "vertical",
                     "color": deco["fill"],
                     "box_w_px": max(1, round((b[2] - b[0]) * k)), "box_h_px": max(1, round((b[3] - b[1]) * k)),
                     "line_gap_ratio": LINE_GAP_RATIO, "decoration": deco, "ruby": t.ruby or []})
        if t.balloon_shape:
            bs = BalloonShape.model_validate(t.balloon_shape)
            if bs.kind != "none":
                if bs.line_width_mm is None or bs.line_color is None:
                    raise RenderRefused(f"フキダシ {t.id} の線（line_width_mm・line_color）が決まっていない")
                bimg = Image.new("RGBA", size, (0, 0, 0, 0))
                ImageDraw.Draw(bimg).polygon(_pts(mm2px, bs.outline_mm),
                                             fill=_hex(bs.fill_color) if bs.fill_color else None,
                                             outline=_hex(bs.line_color), width=max(1, round(bs.line_width_mm * k)))
                bbox = bimg.getbbox()
                if bbox:
                    balloons.append(Node(LAYER_NAME_BALLOON, f"{t.id}-balloon", bimg.crop(bbox), bbox[0], bbox[1],
                                         table="text_items"))
    rendered = render_texts(jobs) if jobs else []
    for t, job, img in zip(texts, jobs, rendered):
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
                "font_name": t.font_family or prefs["fonts_by_kind"][t.item_kind], "font_size": job["font_size_px"],
                "color_rgb": list(_hex(job["color"])[:3]), "x": float(left), "y": float(top)}
        node = Node(t.speaker or t.item_kind, t.id, timg, left, top, blend_mode_of(t.adjustments or []), t.opacity,
                    text=info, table="text_items")
        (sfx if t.item_kind == "drawn_sfx" else typeset).append(node)
    nodes.append(Node(LAYER_NAME_BALLOON, f"{pid}-balloons", children=balloons))
    nodes.append(Node(LAYER_NAME_TYPESET, f"{pid}-typeset", children=typeset))
    nodes.append(Node(LAYER_NAME_SFX, f"{pid}-sfx", children=sfx))
    return RenderedPage(size[0], size[1], nodes, composite(nodes, size))
