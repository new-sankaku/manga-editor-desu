"""画素の消しゴム：AIの絵の層（線を持たない絵）を消す（V3細部の決めごと 10.1 のペン・消しゴム）。

人の手の層の線は、線の消しゴム（hand_tools/vector_strokes.py）で消す。こちらは絵そのものを消すので、答えは新しい版の絵。
消した所はマスクで返し、新しい版の人の手の範囲にする（AIが描き直すとき、その所は描き直さない）。
消しゴムは丸い筆で、線の所の不透明さを不透明度の分だけ減らす。
"""

import io
import math
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image, ImageDraw
from pydantic import BaseModel, ConfigDict, Field


class PixelEraserStroke(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 絵の画素の座標
    points: list[tuple[float, float]] = Field(min_length=1)
    width_px: float = Field(gt=0)
    opacity: float = Field(default=1.0, gt=0, le=1)


def _stroke_box(size: tuple[int, int], s: PixelEraserStroke) -> tuple[int, int, int, int] | None:
    """線が触れうる範囲（整数の画素。絵の外は切る）。範囲の外は描いても 0 なので、範囲の中だけで描いて重ねる。"""
    r = s.width_px / 2 + 2
    xs = [x for x, _ in s.points]
    ys = [y for _, y in s.points]
    x0, y0 = max(0, math.floor(min(xs) - r)), max(0, math.floor(min(ys) - r))
    x1, y1 = min(size[0], math.ceil(max(xs) + r) + 1), min(size[1], math.ceil(max(ys) + r) + 1)
    return (x0, y0, x1, y1) if x0 < x1 and y0 < y1 else None


def _stroke_mask(box: tuple[int, int, int, int], s: PixelEraserStroke) -> np.ndarray:
    """範囲 box の中の線のマスク（0〜255）。座標を整数だけずらして描くので、絵全体に描いたときと同じ画素になる。"""
    x0, y0, x1, y1 = box
    m = Image.new("L", (x1 - x0, y1 - y0), 0)
    d = ImageDraw.Draw(m)
    r = s.width_px / 2
    pts = [(x - x0, y - y0) for x, y in s.points]
    if len(pts) > 1:
        d.line(pts, fill=255, width=max(1, round(s.width_px)), joint="curve")
    for x, y in pts:
        d.ellipse((x - r, y - r, x + r, y + r), fill=255)
    return np.asarray(m)


def _png(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def erase_pixels(base_png: bytes, strokes: list[PixelEraserStroke]) -> tuple[bytes, bytes]:
    """(消した後の PNG, 消した所のマスクの PNG。白が消した所)。
    線ごとの計算は線の範囲の中だけで行う（4960×7016 の絵で、絵全体を線の数だけ作り直さない）。
    2つの PNG は別の糸で同時に書く（PNG を書く zlib は GIL を離す。書く所が保存の時間のほとんど）。"""
    im = Image.open(io.BytesIO(base_png)).convert("RGBA")
    alpha = np.array(im.getchannel("A"))
    # 消した所を 255 にする。np.where(真偽, 255, 0) は int64 の配列（35M 画素で 280MB）を作り、それだけで 1〜3 秒かかった
    erased = np.zeros(alpha.shape, dtype=np.uint8)
    for s in strokes:
        box = _stroke_box(im.size, s)
        if box is None:
            continue
        x0, y0, x1, y1 = box
        mask = _stroke_mask(box, s)
        # 今までの ImageChops.subtract(alpha, round(mask * opacity)) と同じ（丸めは偶数への丸め・0 で止める）
        cut = np.rint(mask * s.opacity).astype(np.int16)
        part = alpha[y0:y1, x0:x1]
        alpha[y0:y1, x0:x1] = np.clip(part.astype(np.int16) - cut, 0, 255).astype(np.uint8)
        erased[y0:y1, x0:x1][mask > 0] = 255
    im.putalpha(Image.fromarray(alpha, "L"))
    erased_im = Image.fromarray(erased, "L")
    with ThreadPoolExecutor(max_workers=2) as pool:
        out, mask_png = pool.map(_png, (im, erased_im))
    return out, mask_png
