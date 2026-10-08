"""入稿用 PDF を書く（img2pdf と pypdf）。計算だけの部品。寸法と dpi は呼ぶ側が PageSpec と引数で渡す。

試作 p51 で確かめたこと:
- ページの大きさを mm で指定すると、画素数が割り切れなくても 188.000x263.000mm に合う
  （dpi 情報どおりにすると 600dpi で 0.017mm・350dpi で 0.033mm ずれた）。
- 2値の画像は Flate（PNG）でも CCITT G4（TIFF）でも可逆（poppler で取り出して全画素一致）。
  グレー・カラーは Flate で可逆。
- TrimBox・BleedBox は pypdf で足せる。
"""
import io
import pathlib
from collections.abc import Sequence
from typing import Literal

import img2pdf
import numpy as np
import pypdf
from PIL import Image

from v3server.name_structure.reading_direction import PageSpec
from v3server.print_export.cmyk_conversion import cmyk_tiff_bytes

BilevelCodec = Literal["flate", "ccitt_g4"]

_MM_PER_INCH = 25.4
_PT_PER_INCH = 72.0


def canvas_size_mm(spec: PageSpec) -> tuple[float, float]:
    """塗り足しを含む1ページの寸法（mm）。"""
    return (spec.trim_width_mm + 2 * spec.bleed_mm, spec.trim_height_mm + 2 * spec.bleed_mm)


def canvas_size_px(spec: PageSpec, dpi: float) -> tuple[int, int]:
    """塗り足しを含む1ページの画素数。"""
    w, h = canvas_size_mm(spec)
    return (round(w / _MM_PER_INCH * dpi), round(h / _MM_PER_INCH * dpi))


def _encode_page(image: Image.Image, bilevel_codec: BilevelCodec | None, dpi: float) -> bytes:
    buf = io.BytesIO()
    if image.mode == "1":
        if bilevel_codec is None:
            raise ValueError("2値のページがあるのに、2値の符号化が決まっていない")
        if bilevel_codec == "ccitt_g4":
            image.save(buf, format="TIFF", compression="group4", dpi=(dpi, dpi))
        elif bilevel_codec == "flate":
            image.save(buf, format="PNG", dpi=(dpi, dpi))
        else:
            raise ValueError(f"2値の符号化が不明です: {bilevel_codec}")
    elif image.mode in ("L", "RGB"):
        image.save(buf, format="PNG", dpi=(dpi, dpi))
    elif image.mode == "CMYK":
        # cmyk_conversion.to_cmyk で作った絵（ICC プロファイル付き）。img2pdf が ICCBased の色空間にする
        if "icc_profile" not in image.info:
            raise ValueError("CMYK のページに ICC プロファイルが付いていない")
        return cmyk_tiff_bytes(image, dpi)
    else:
        raise ValueError(f"画像のモードは 1・L・RGB・CMYK のどれかにしてください（{image.mode}）")
    return buf.getvalue()


def bilevel_image_from_black_mask(black: np.ndarray) -> Image.Image:
    """黒が True の bool 配列から、1ビットの画像（黒=0）を作る。"""
    if black.dtype != bool or black.ndim != 2:
        raise ValueError("bool の2次元配列で渡してください")
    return Image.fromarray((~black).astype(np.uint8) * 255, "L").convert("1", dither=Image.Dither.NONE)


def paper_size_px(paper_mm: tuple[float, float], dpi: float) -> tuple[int, int]:
    return (round(paper_mm[0] / _MM_PER_INCH * dpi), round(paper_mm[1] / _MM_PER_INCH * dpi))


def write_print_pdf(pages: Sequence[Image.Image], spec: PageSpec, dpi: float | Sequence[float],
                    bilevel_codec: BilevelCodec | None, output_path: pathlib.Path,
                    paper_mm: tuple[float, float] | None = None) -> None:
    """塗り足し込みの画像を1ページずつ並べた PDF を書く。dpi はページごとに渡せる（ページで解像度が違う原稿）。
    2値（mode "1"）・グレー（"L"）・カラー（"RGB"）のページを混ぜてよい。2値のページがあるときは bilevel_codec が要る。

    画素数が spec と dpi から計算した値と違うときは例外にする（黙って拡大縮小しない）。
    MediaBox は塗り足し込み（紙の大きさ paper_mm を渡したときは紙）、TrimBox は仕上がり、
    BleedBox は塗り足し込みにする。紙を渡したときは、ページの絵が紙の真ん中に置いてある前提。
    """
    if not pages:
        raise ValueError("ページが1枚もありません")
    canvas_mm = canvas_size_mm(spec)
    if paper_mm is not None and (paper_mm[0] < canvas_mm[0] or paper_mm[1] < canvas_mm[1]):
        raise ValueError(f"紙 {paper_mm}mm が塗り足し込みのページ {canvas_mm}mm より小さい")
    dpis = list(dpi) if isinstance(dpi, (list, tuple)) else [dpi] * len(pages)
    if len(dpis) != len(pages):
        raise ValueError(f"dpi の数 {len(dpis)} がページの数 {len(pages)} と違います")
    for i, (page, d) in enumerate(zip(pages, dpis, strict=False)):
        expected = paper_size_px(paper_mm, d) if paper_mm is not None else canvas_size_px(spec, d)
        if page.size != expected:
            raise ValueError(f"{i + 1}ページ目の画素数 {page.size} が、寸法と dpi から計算した {expected} と違います")
    w_mm, h_mm = paper_mm if paper_mm is not None else canvas_mm
    layout = img2pdf.get_layout_fun((img2pdf.mm_to_pt(w_mm), img2pdf.mm_to_pt(h_mm)))
    raw = img2pdf.convert([_encode_page(p, bilevel_codec, d) for p, d in zip(pages, dpis, strict=False)], layout_fun=layout)

    reader = pypdf.PdfReader(io.BytesIO(raw))
    writer = pypdf.PdfWriter()
    writer.append_pages_from_reader(reader)
    bleed_pt = spec.bleed_mm / _MM_PER_INCH * _PT_PER_INCH
    mx = (w_mm - canvas_mm[0]) / 2 / _MM_PER_INCH * _PT_PER_INCH
    my = (h_mm - canvas_mm[1]) / 2 / _MM_PER_INCH * _PT_PER_INCH
    for page in writer.pages:
        media = page.mediabox
        left, bottom = float(media.left) + mx, float(media.bottom) + my
        right, top = float(media.right) - mx, float(media.top) - my
        page.bleedbox = pypdf.generic.RectangleObject([left, bottom, right, top])
        page.trimbox = pypdf.generic.RectangleObject([left + bleed_pt, bottom + bleed_pt, right - bleed_pt, top - bleed_pt])
    with open(output_path, "wb") as f:
        writer.write(f)
