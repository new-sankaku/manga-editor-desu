"""画素の消しゴム：AIの絵の層（線を持たない絵）を消す（V3細部の決めごと 10.1 のペン・消しゴム）。

人の手の層の線は、線の消しゴム（hand_tools/vector_strokes.py）で消す。こちらは絵そのものを消すので、答えは新しい版の絵。
消した所はマスクで返し、新しい版の人の手の範囲にする（AIが描き直すとき、その所は描き直さない）。
消しゴムは丸い筆で、線の所の不透明さを不透明度の分だけ減らす。
"""

import io

from PIL import Image, ImageChops, ImageDraw
from pydantic import BaseModel, ConfigDict, Field


class PixelEraserStroke(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 絵の画素の座標
    points: list[tuple[float, float]] = Field(min_length=1)
    width_px: float = Field(gt=0)
    opacity: float = Field(default=1.0, gt=0, le=1)


def _stroke_mask(size: tuple[int, int], s: PixelEraserStroke) -> Image.Image:
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    r = s.width_px / 2
    if len(s.points) > 1:
        d.line(s.points, fill=255, width=max(1, round(s.width_px)), joint="curve")
    for x, y in s.points:
        d.ellipse((x - r, y - r, x + r, y + r), fill=255)
    return m


def erase_pixels(base_png: bytes, strokes: list[PixelEraserStroke]) -> tuple[bytes, bytes]:
    """(消した後の PNG, 消した所のマスクの PNG。白が消した所)。"""
    im = Image.open(io.BytesIO(base_png)).convert("RGBA")
    erased = Image.new("L", im.size, 0)
    for s in strokes:
        mask = _stroke_mask(im.size, s)
        cut = mask.point(lambda v, o=s.opacity: round(v * o))
        im.putalpha(ImageChops.subtract(im.getchannel("A"), cut))
        erased = ImageChops.lighter(erased, mask)
    out, mbuf = io.BytesIO(), io.BytesIO()
    im.save(out, format="PNG")
    erased.point(lambda v: 255 if v else 0).save(mbuf, format="PNG")
    return out.getvalue(), mbuf.getvalue()
