"""ページの色の種類（2階調・グレー・カラー）に合わせて、書き出す絵を作る（V3細部の決めごと 3章）。

- カラー：層を重ねた RGB のまま
- グレー：重ねた絵を L（8ビットの灰色）にする
- 2階調：層ごとに白黒にしてから重ね、1ビットの絵にする。
  線・ベタ・文字・人の手・コマ枠・フキダシ・トーン・図形は閾値で、コマの絵と見開きの絵と、
  絵の層（線画・ベタ・文字・人の手の層を除く）は網点（BilevelSettings.image_screen）で白黒にする。
  重ねた後で網点にすると線の縁が点々に切れるので、層ごとに分ける（binarize_and_halftone.py の試作 p51 の結果）。
  網の目はページの画素で揃える（層の置き場を網点の原点に渡す）。

PSD はどの色の種類でも層のまま RGB で出す（2階調・グレーの PSD は作らない。印刷所へは PNG・PDF で渡す）。
"""

from dataclasses import replace

import numpy as np
from PIL import Image

from v3server.name_structure.print_settings import BilevelSettings
from v3server.print_export.binarize_and_halftone import binarize, halftone_screen
from v3server.print_export.page_render import LAYER_NAME_PANEL_IMAGE, LAYER_NAME_SPREAD_IMAGE, Node, composite

# 絵の層のうち、閾値で白黒にするもの（ほかの役は網点）
THRESHOLD_LAYER_ROLES = {"line_art", "solid_black", "text", "human_hand"}
SCREEN_LAYER_ROLES = {"panel_art", "tone", "color", "background", "effect"}


class ColorModeError(ValueError):
    pass


def _uses_screen(n: Node) -> bool:
    if n.table == "panels":
        return n.name == LAYER_NAME_PANEL_IMAGE
    if n.table == "spreads":
        return n.name == LAYER_NAME_SPREAD_IMAGE
    if n.table == "panel_layers":
        if n.name in THRESHOLD_LAYER_ROLES:
            return False
        if n.name in SCREEN_LAYER_ROLES:
            return True
        raise ColorModeError(f"層 {n.marker} の役 {n.name} を、2階調で閾値にするか網点にするか決めていない")
    return False


def _bilevel_leaf(n: Node, dpi: float, bs: BilevelSettings) -> Node:
    """層1つを、黒（0）か白（255）で、見えるか見えないかだけの絵にする。"""
    rgba = np.asarray(n.image.convert("RGBA"), np.float32) / 255
    alpha = rgba[..., 3] * n.opacity
    # 色は白の上に置いたときの明るさで見る（半透明の縁も、白に溶けた明るさで白黒を決める）
    lum = rgba[..., 0] * 0.299 + rgba[..., 1] * 0.587 + rgba[..., 2] * 0.114
    gray = np.clip(lum * 255 + 0.5, 0, 255).astype(np.uint8)
    if _uses_screen(n):
        sc = bs.image_screen
        black = halftone_screen(gray, dpi, sc.lines_per_inch, sc.angle_deg, sc.dot_shape, origin_px=(n.left, n.top))
    else:
        black = binarize(gray, bs.threshold)
    out = np.empty(gray.shape + (4,), np.uint8)
    out[..., :3] = np.where(black, 0, 255)[..., None]
    out[..., 3] = np.where(alpha >= 0.5, 255, 0)
    return replace(n, image=Image.fromarray(out, "RGBA"), opacity=1.0)


def _bilevel_nodes(nodes: list[Node], dpi: float, bs: BilevelSettings) -> list[Node]:
    out = []
    for n in nodes:
        if n.children is not None:
            out.append(replace(n, children=_bilevel_nodes(n.children, dpi, bs)))
        elif n.image is None or n.hidden:
            out.append(n)
        else:
            out.append(_bilevel_leaf(n, dpi, bs))
    return out


def page_image(nodes: list[Node], size: tuple[int, int], color_mode: str, dpi: float,
               bilevel: BilevelSettings | None) -> Image.Image:
    """層から、色の種類の絵を作る（2階調は mode "1"、グレーは "L"、カラーは "RGB"）。"""
    if color_mode == "color":
        return composite(nodes, size)
    if color_mode == "grayscale":
        return composite(nodes, size).convert("L")
    if color_mode == "bilevel":
        if bilevel is None:
            raise ColorModeError("2階調のページがあるのに、2階調にする決まり（作品の preferences.print.bilevel）が無い")
        flat = composite(_bilevel_nodes(nodes, dpi, bilevel), size).convert("L")
        black = np.asarray(flat) < 128
        return Image.fromarray((~black).astype(np.uint8) * 255, "L").convert("1", dither=Image.Dither.NONE)
    raise ColorModeError(f"知らない色の種類: {color_mode}")
