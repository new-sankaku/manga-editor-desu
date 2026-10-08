"""白黒の絵を、線・ベタ・トーンの3つの層に分ける。移す元は試作 p20 `analyze.py` の `split`。

線は、絵から抜いた線画（`comfy_graphs/line_extract_graph.py`、黒地に白い線）で決める。
線でない所を濃さで、ベタ・トーン・紙の白に分ける。閾値はコードに書かず、Threshold の表から渡す。

試作 p20 で分かったこと：
- 重ね直した絵と元の絵の差は平均 6.2/255（Manga2Anime の線画）。
- トーンの層は網点ではなく灰色の階調になる。印刷する前に網点に直す工程が要る。
- ベタの層に、背景の暗いぼかしが混じる。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

# 層の中で何も無い所（紙の白）
BLANK = 255


@dataclass(frozen=True)
class SplitThresholds:
    """分ける閾値（0〜255）。Threshold の表から読む。

    solid_below：これより暗い画素はベタ。
    paper_white_from：これ以上明るい画素は紙の白（どの層にも入れない）。
    line_on_from：線画（黒地に白い線）で、これ以上明るい画素を線とみなす。
    line_value_ceiling：線の層の濃さの上限。線の所の元の画素がこれより明るくても、この濃さで描く。
    """

    solid_below: int
    paper_white_from: int
    line_on_from: int
    line_value_ceiling: int


@dataclass(frozen=True)
class LayerSplit:
    """3つの層（どれも白地に黒の濃さ、uint8）と、重ね直した絵、各層の画素の割合。"""

    line: np.ndarray
    solid: np.ndarray
    tone: np.ndarray
    recomposed: np.ndarray
    line_ratio: float
    solid_ratio: float
    tone_ratio: float


def grey_array(image: Image.Image, size: tuple[int, int]) -> np.ndarray:
    """画像を灰色の uint8 の配列にする。大きさが違えば lanczos で合わせる（線画は元の絵と大きさが違うことがある）。"""
    im = image.convert('L')
    if im.size != size:
        im = im.resize(size, Image.Resampling.LANCZOS)
    return np.asarray(im, dtype=np.uint8)


def split_line_solid_tone(picture: np.ndarray, line_art: np.ndarray, th: SplitThresholds) -> LayerSplit:
    """picture（白黒の絵、灰色の uint8）を、line_art（黒地に白い線、同じ大きさ）を使って3層に分ける。"""
    if picture.ndim != 2 or line_art.ndim != 2:
        raise ValueError('絵と線画は灰色の2次元の配列で渡してください')
    if picture.shape != line_art.shape:
        raise ValueError(f'絵 {picture.shape} と線画 {line_art.shape} の大きさが違います')
    if not th.solid_below <= th.paper_white_from:
        raise ValueError('ベタの閾値が紙の白の閾値より明るくなっています')
    pic = picture.astype(np.int16)
    is_line = line_art >= th.line_on_from
    is_solid = (pic < th.solid_below) & ~is_line
    is_tone = (pic >= th.solid_below) & (pic < th.paper_white_from) & ~is_line
    line = np.where(is_line, np.minimum(pic, th.line_value_ceiling), BLANK)
    solid = np.where(is_solid, 0, BLANK)
    tone = np.where(is_tone, pic, BLANK)
    recomposed = np.minimum(np.minimum(line, solid), tone)
    return LayerSplit(
        line=line.astype(np.uint8),
        solid=solid.astype(np.uint8),
        tone=tone.astype(np.uint8),
        recomposed=recomposed.astype(np.uint8),
        line_ratio=float(is_line.mean()),
        solid_ratio=float(is_solid.mean()),
        tone_ratio=float(is_tone.mean()),
    )


def mean_difference(picture: np.ndarray, recomposed: np.ndarray) -> float:
    """元の絵と重ね直した絵の差の平均（0〜255）。分け方で失った量の目安。"""
    if picture.shape != recomposed.shape:
        raise ValueError('大きさが違います')
    return float(np.abs(picture.astype(np.int16) - recomposed.astype(np.int16)).mean())
