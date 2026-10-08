"""枠と番号だけのラフ画像を描く（試作 p11・p31・p45・p12 の描画をまとめた。V3ハーネス設計 5.3「ラフでの確認」）。
画像生成を通さないので、安く何度でも描き直せる。読む順や角度を画像から判定させる問い（llm_questions）にもこの絵を渡す。
描くもの：コマの枠（多角形）、任意でコマの番号・人物の範囲の目印・吹き出しの楕円とセリフ。"""
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from v3server.name_structure.name_draft_schema import NamePage
from v3server.name_structure.reading_direction import PageSpec
from v3server.panel_layout.panel_geometry import (
    Box,
    Polygon,
    polygon_bbox,
    shrink_polygon,
    vertex_mean,
)


@dataclass(frozen=True)
class RoughStyle:
    """描き方。値は呼ぶ側が決める（ここに既定の値は置かない）。"""

    px_per_mm: float
    line_px: int
    # コマの番号を描くか。読む順を絵から判定させるときは描かない（試作 p11・p45）
    show_numbers: bool
    # 番号とセリフの字の大きさ（px）
    font_px: int
    # 番号とセリフに使う字体のファイル。日本語のセリフを描くなら日本語の字体が要る。None なら Pillow の内蔵の字体（英数字だけ）
    font_path: str | None
    # 枠を頂点の平均へ寄せる距離（mm）。斜めのコマで隣との隙間を見せる（試作 p45）。None なら寄せない
    shrink_mm: float | None
    show_figures: bool
    show_balloons: bool
    # 吹き出しの中にセリフを描くか。False なら文字の代わりに線を引く（試作 p31）
    show_balloon_text: bool


def _font(style: RoughStyle) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if style.font_path is None:
        return ImageFont.load_default(style.font_px)
    return ImageFont.truetype(style.font_path, style.font_px)


class _Canvas:
    """仕上がりと塗り足しを含む紙。基本枠の座標（mm）を画素に直す。"""

    def __init__(self, spec: PageSpec, style: RoughStyle):
        self.spec, self.style = spec, style
        ox, oy = spec.frame_origin_in_trim()
        # 紙の左上から見た基本枠の左上（mm）
        self.offset = (ox + spec.bleed_mm, oy + spec.bleed_mm)
        w = (spec.trim_width_mm + 2 * spec.bleed_mm) * style.px_per_mm
        h = (spec.trim_height_mm + 2 * spec.bleed_mm) * style.px_per_mm
        self.image = Image.new("RGB", (round(w), round(h)), "white")
        self.draw = ImageDraw.Draw(self.image)

    def px(self, x: float, y: float) -> tuple[float, float]:
        s = self.style.px_per_mm
        return (x + self.offset[0]) * s, (y + self.offset[1]) * s

    def box_px(self, b: Box) -> tuple[float, float, float, float]:
        x0, y0 = self.px(b[0], b[1])
        x1, y1 = self.px(b[2], b[3])
        return x0, y0, x1, y1

    def guides(self) -> None:
        """仕上がりの線と基本枠を灰色で描く。"""
        W, H = self.spec.frame_width_mm, self.spec.frame_height_mm
        ox, oy = self.spec.frame_origin_in_trim()
        self.draw.rectangle(self.box_px((-ox, -oy, W + ox, H + oy)), outline=(170, 170, 170), width=1)
        self.draw.rectangle(self.box_px((0, 0, W, H)), outline=(200, 200, 200), width=1)


def draw_polygons(polygons: dict[int, Polygon], spec: PageSpec, style: RoughStyle) -> Image.Image:
    """コマの枠だけを描く。polygons は {コマの番号: 頂点（基本枠の座標・mm）}。"""
    c = _Canvas(spec, style)
    _draw_frames(c, polygons)
    return c.image


def _draw_frames(c: _Canvas, polygons: dict[int, Polygon]) -> None:
    style = c.style
    c.guides()
    font = _font(style) if style.show_numbers else None
    for n, poly in polygons.items():
        pts = shrink_polygon(poly, style.shrink_mm) if style.shrink_mm is not None else list(poly)
        q = [c.px(x, y) for x, y in pts]
        c.draw.polygon(q, fill="white", outline="black", width=style.line_px)
        if font is not None:
            cx, cy = c.px(*vertex_mean(pts))
            c.draw.text((cx, cy), str(n), fill="black", font=font, anchor="mm")


def _balloon_lines(c: _Canvas, box: Box) -> None:
    """文字の代わりに縦の線を引く（右から読む縦書きの見た目。試作 p31・p47）。"""
    x0, y0, x1, y1 = c.box_px(box)
    w, h = x1 - x0, y1 - y0
    for k in range(3):
        x = x1 - w * (0.3 + 0.2 * k)
        c.draw.line((x, y0 + h * 0.25, x, y1 - h * 0.25), fill="black", width=c.style.line_px)


def _balloon_text(c: _Canvas, box: Box, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> None:
    """セリフを縦書きで、右の列から描く。楕円からはみ出すかは確かめない（ラフなので）。"""
    x0, y0, x1, y1 = c.box_px(box)
    step = c.style.font_px * 1.1
    per_col = max(1, int((y1 - y0) * 0.7 // step))
    cols = [text[i:i + per_col] for i in range(0, len(text), per_col)]
    x = (x0 + x1) / 2 + (len(cols) - 1) * step / 2
    for col in cols:
        y = (y0 + y1) / 2 - (len(col) - 1) * step / 2
        for ch in col:
            c.draw.text((x, y), ch, fill="black", font=font, anchor="mm")
            y += step
        x -= step


def draw_page_rough(page: NamePage, spec: PageSpec, style: RoughStyle) -> Image.Image:
    """ネームの1ページのラフ。枠はコマ割りの計算（tier_ratio_layout）の後にだけあるので、枠の無いコマがあれば例外にする。"""
    missing = [p.n for p in page.panels if p.frame is None]
    if missing:
        raise ValueError(f"{page.page}ページ：枠の無いコマがある {missing}")
    c = _Canvas(spec, style)
    _draw_frames(c, {p.n: p.frame.polygon_mm for p in page.panels})
    font = _font(style)
    for p in page.panels:
        if style.show_figures:
            for f in p.people:
                if f.box_mm is not None:
                    c.draw.rectangle(c.box_px(f.box_mm), outline=(120, 120, 120), width=max(1, style.line_px // 2))
                    x0, y0, _, _ = c.box_px(f.box_mm)
                    c.draw.text((x0 + 2, y0 + 2), f.name, fill=(120, 120, 120), font=font)
                if f.face_box_mm is not None:
                    c.draw.ellipse(c.box_px(f.face_box_mm), outline=(120, 120, 120), width=max(1, style.line_px // 2))
        if style.show_balloons:
            for b in p.balloons:
                if b.box_mm is None:
                    continue
                c.draw.ellipse(c.box_px(b.box_mm), fill="white", outline="black", width=style.line_px)
                if style.show_balloon_text:
                    _balloon_text(c, b.box_mm, b.text, font)
                else:
                    _balloon_lines(c, b.box_mm)
    return c.image


def polygons_bbox_px(polygons: dict[int, Polygon], spec: PageSpec, style: RoughStyle) -> dict[int, Box]:
    """各コマの外接する四角を画素で返す。画像を見た答え（座標）をコマに割り当てるときに使う。"""
    c = _Canvas(spec, style)
    return {n: c.box_px(polygon_bbox(poly)) for n, poly in polygons.items()}
