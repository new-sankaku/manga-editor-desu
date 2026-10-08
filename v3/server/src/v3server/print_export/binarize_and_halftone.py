"""灰色を2値（閾値）や網点（線数・角度・形）にする。計算だけで、画像は numpy の配列で受け渡す。

画像は uint8 の2次元（255=白）。結果は bool（True=黒）。

試作 p51 で分かったこと（合成の絵での測定。実際の漫画の絵では未検証）:
- 閾値で2値にすると、細い線は位置で消える。600dpi・閾値128で 0.03mm は消え、0.05mm は
  画素の格子との位置で消えるか1画素で残る。0.1mm 以上は残った。閾値を上げる（線が残りやすい）と
  線は1画素ほど太る。閾値は引数で受け取り、ここでは決めない。
- 網点を高い dpi で作ってから低い dpi に縮めて2値にすると、黒の割合が下がる（600→350dpi、
  30%の目標に対し 28.8%（60線）・28.0%（85線））。低い dpi で出す画像は、その dpi で網点を作る。
- セルの一辺（画素）= dpi / 線数。350dpi・85線は4.1画素で粗い。
- Pillow・OpenCV・scikit-image には線数と角度を指定する網点が無い。ImageMagick は固定の閾値表のみ。
  そのため numpy で書いた。
"""
from functools import cache
from typing import Literal

import numpy as np

DotShape = Literal["round", "line", "square"]

# 1つの網点セルの閾値表の分解能
_CELL_SIZE = 256
# 行をまとめて処理して、大きな原稿でも一時的な配列を抑える
_ROWS_PER_CHUNK = 512


def _check_gray(gray: np.ndarray) -> None:
    if gray.ndim != 2 or gray.dtype != np.uint8:
        raise ValueError("灰色の画像は uint8 の2次元配列で渡してください")


@cache
def _threshold_cell(shape: str) -> np.ndarray:
    """網点セルの閾値表（0..1）。面積が濃度に比例するように、値の順位で並べ直す。"""
    u, v = np.meshgrid((np.arange(_CELL_SIZE) + 0.5) / _CELL_SIZE, (np.arange(_CELL_SIZE) + 0.5) / _CELL_SIZE)
    if shape == "round":
        f = 1 - (np.cos(2 * np.pi * u) + np.cos(2 * np.pi * v) + 2) / 4
    elif shape == "line":
        f = 1 - (np.cos(2 * np.pi * v) + 1) / 2
    elif shape == "square":
        # 中心からの四角い距離（四角い点が大きくなる）
        du = np.abs(u - 0.5) * 2
        dv = np.abs(v - 0.5) * 2
        f = 1 - np.maximum(1 - du, 1 - dv)
    else:
        raise ValueError(f"網点の形が不明です: {shape}")
    ranks = np.argsort(np.argsort(f.ravel())).reshape(f.shape)
    cell = (ranks + 0.5) / f.size
    cell.setflags(write=False)
    return cell


def halftone_screen(gray: np.ndarray, dpi: float, lines_per_inch: float, angle_deg: float, dot_shape: DotShape) -> np.ndarray:
    """灰色を、線数・角度・形を指定した網点で2値にする。True=黒。

    黒の面積は元の濃度にほぼ比例する（p51：600・350dpi、60・85線、10〜90%で誤差0.004以内）。
    """
    _check_gray(gray)
    if dpi <= 0 or lines_per_inch <= 0:
        raise ValueError("dpi と線数は正の数で渡してください")
    cell = _threshold_cell(dot_shape)
    period = dpi / lines_per_inch
    a = np.radians(angle_deg)
    cos_a, sin_a = float(np.cos(a)), float(np.sin(a))
    height, width = gray.shape
    xs = np.arange(width, dtype=np.float32)[None, :]
    out = np.empty((height, width), dtype=bool)
    for top in range(0, height, _ROWS_PER_CHUNK):
        bottom = min(height, top + _ROWS_PER_CHUNK)
        ys = np.arange(top, bottom, dtype=np.float32)[:, None]
        u = (xs * cos_a + ys * sin_a) / period
        v = (-xs * sin_a + ys * cos_a) / period
        iu = np.floor((u % 1) * _CELL_SIZE).astype(np.intp) % _CELL_SIZE
        iv = np.floor((v % 1) * _CELL_SIZE).astype(np.intp) % _CELL_SIZE
        dark = 1 - gray[top:bottom].astype(np.float32) / 255
        out[top:bottom] = dark > cell[iv, iu]
    return out


def binarize(gray: np.ndarray, threshold: int) -> np.ndarray:
    """閾値より暗い画素を黒（True）にする。閾値は 1..255。"""
    _check_gray(gray)
    if not 1 <= threshold <= 255:
        raise ValueError("閾値は 1 から 255 で渡してください")
    return gray < threshold


def compose_line_and_tone(line_gray: np.ndarray, tone_gray: np.ndarray, line_threshold: int, dpi: float,
                          lines_per_inch: float, angle_deg: float, dot_shape: DotShape) -> np.ndarray:
    """線の層は閾値で、トーンの層は網点で2値にして重ねる（黒が勝つ）。True=黒。

    線を網点に通すと縁が点々に切れるので、層を分けて別々に2値にする。
    """
    if line_gray.shape != tone_gray.shape:
        raise ValueError("線の層とトーンの層の大きさが違います")
    return binarize(line_gray, line_threshold) | halftone_screen(tone_gray, dpi, lines_per_inch, angle_deg, dot_shape)
