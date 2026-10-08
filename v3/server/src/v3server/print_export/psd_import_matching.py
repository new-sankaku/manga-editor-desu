"""人が直した PSD を読み、書き出したときの層と結び付ける（答えが決まる計算だけ。正本は変えない）。

読むのは psd-tools。書き出しの層の名前は「名前 [id]」（print_export/page_render.py）。試作 p59 で分かったこと：
- Krita は層の名前の後ろに NUL を足す。GIMP は同じ名前の層に「 #1」などを足す。どちらも外してから読む
- [id] の印は、人が名前を変えた・消した層の外では残った
結び付け方：
- 印のある層：書き出したときの画素と同じなら unchanged、違えば changed
- 印の無い層（名前を変えた層・新しい層）：画素が、印の付いた層のうち PSD に無くなった物と同じなら renamed。
  それ以外は new（親のグループの印を持たせる。コマのグループなら、そのコマに人の手の層として入れる）
- 書き出したのに PSD に無い層：missing
画素が同じかは、両方をページの画素に置いて、見える所（不透明度 0 より大）の RGBA が全部同じか、で決める（ずれを許さない）。
描き直さずに保存しても画素が変わる道具があれば、そこでは changed になる（未検証）。
"""

import io
import re
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from PIL import Image

MARKER_RE = re.compile(r"\[([0-9a-f]{32}(?:-[a-z]+)?)\]\s*$")
_GIMP_SUFFIX_RE = re.compile(r" #\d+$")


def clean_name(raw: str) -> str:
    """末尾の NUL と、GIMP の「 #n」を外す。"""
    name = raw.rstrip("\x00").rstrip()
    return _GIMP_SUFFIX_RE.sub("", name)


def marker_of(name: str) -> str | None:
    m = MARKER_RE.search(clean_name(name))
    return m.group(1) if m else None


@dataclass
class ReadLayer:
    name: str
    marker: str | None
    # 親のグループの印（いちばん近い、印のあるグループ）
    parent_marker: str | None
    left: int
    top: int
    image: Image.Image | None
    is_group: bool = False


@dataclass
class ExportedLayer:
    """書き出したときの層（ExportRun.outputs の layers）。"""

    marker: str
    table: str | None
    left: int
    top: int
    image: Image.Image


@dataclass
class Match:
    kind: Literal["unchanged", "changed", "renamed", "new", "missing"]
    marker: str | None = None
    layer: ReadLayer | None = None
    exported: ExportedLayer | None = None
    extra: dict = field(default_factory=dict)


def read_psd(data: bytes) -> list[ReadLayer]:
    from psd_tools import PSDImage

    psd = PSDImage.open(io.BytesIO(data))
    out: list[ReadLayer] = []

    def walk(group, parent_marker):
        for layer in group:
            name = clean_name(layer.name)
            marker = marker_of(name)
            if layer.is_group():
                out.append(ReadLayer(name, marker, parent_marker, 0, 0, None, True))
                walk(layer, marker or parent_marker)
                continue
            img = layer.topil()
            left, top = layer.left, layer.top
            if img is None:
                img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            out.append(ReadLayer(name, marker, parent_marker, left, top, img.convert("RGBA")))

    walk(psd, None)
    return out


def _canvas(img: Image.Image, left: int, top: int, box: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = box
    c = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    c.paste(img, (left - x0, top - y0))
    a = np.asarray(c).copy()
    a[a[..., 3] == 0] = 0
    return a


def same_pixels(a: Image.Image, a_left: int, a_top: int, b: Image.Image, b_left: int, b_top: int) -> bool:
    ab, bb = a.getchannel("A").getbbox(), b.getchannel("A").getbbox()
    if ab is None or bb is None:
        return ab is None and bb is None
    box = (min(a_left + ab[0], b_left + bb[0]), min(a_top + ab[1], b_top + bb[1]),
           max(a_left + ab[2], b_left + bb[2]), max(a_top + ab[3], b_top + bb[3]))
    return np.array_equal(_canvas(a, a_left, a_top, box), _canvas(b, b_left, b_top, box))


def crop_to(layer: ReadLayer, left: int, top: int, width: int, height: int) -> Image.Image:
    """PSD の層を、書き出したときの層の範囲に切る（範囲の外へ描いた所は入らない）。"""
    c = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    c.paste(layer.image, (layer.left - left, layer.top - top))
    return c


def match_layers(read: list[ReadLayer], exported: dict[str, ExportedLayer]) -> list[Match]:
    out: list[Match] = []
    seen: set[str] = set()
    unmarked: list[ReadLayer] = []
    for layer in read:
        if layer.is_group:
            continue
        if layer.marker and layer.marker in exported and layer.marker not in seen:
            seen.add(layer.marker)
            ex = exported[layer.marker]
            same = same_pixels(layer.image, layer.left, layer.top, ex.image, ex.left, ex.top)
            out.append(Match("unchanged" if same else "changed", layer.marker, layer, ex))
        else:
            unmarked.append(layer)
    gone = {m: ex for m, ex in exported.items() if m not in seen}
    for layer in unmarked:
        renamed = next((m for m, ex in gone.items()
                        if same_pixels(layer.image, layer.left, layer.top, ex.image, ex.left, ex.top)), None)
        if renamed is not None:
            out.append(Match("renamed", renamed, layer, gone.pop(renamed)))
        elif layer.image.getchannel("A").getbbox() is not None:
            out.append(Match("new", None, layer))
    for m, ex in gone.items():
        out.append(Match("missing", m, None, ex))
    return out


@dataclass
class ImportAction:
    """戻しの操作（operations/psd_import_operations.py の ApplyPsdImport）に渡す1件。image は置き場に置く前の絵。
    - changed：印の層の画素が変わった（書き出したときの範囲に切った絵）
    - new：印の無い新しい層（parent_marker は親のグループの印）
    - missing：書き出したのに PSD に無い層"""

    kind: Literal["changed", "new", "missing"]
    marker: str | None
    table: str | None
    image: Image.Image | None = None
    # 絵を置く範囲（基本枠の mm の [x0, y0, x1, y1]）
    box_mm: tuple[float, float, float, float] | None = None
    parent_marker: str | None = None
    layer_name: str | None = None


def import_actions(matches: list[Match], px_to_mm) -> list[ImportAction]:
    """px_to_mm(x, y) は PSD の画素（紙の上）→ 基本枠の mm。unchanged・renamed は何もしない（画素が同じ）。"""

    def box(left, top, w, h):
        x0, y0 = px_to_mm(left, top)
        x1, y1 = px_to_mm(left + w, top + h)
        return (x0, y0, x1, y1)

    out = []
    for m in matches:
        if m.kind == "changed":
            ex = m.exported
            img = crop_to(m.layer, ex.left, ex.top, ex.image.width, ex.image.height)
            out.append(ImportAction("changed", m.marker, ex.table, img, box(ex.left, ex.top, img.width, img.height),
                                    layer_name=m.layer.name))
        elif m.kind == "new":
            la = m.layer
            bb = la.image.getchannel("A").getbbox()
            img = la.image.crop(bb)
            out.append(ImportAction("new", None, None, img, box(la.left + bb[0], la.top + bb[1], img.width, img.height),
                                    parent_marker=la.parent_marker, layer_name=la.name))
        elif m.kind == "missing":
            out.append(ImportAction("missing", m.marker, m.exported.table))
    return out
