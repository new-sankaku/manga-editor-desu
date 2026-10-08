"""人の手の範囲（多角形・絵の画素の座標）から、描き直しの手順（protected_redraw_graph.py）に渡すマスクの絵を描く。
白が人の範囲、黒がそれ以外。手順は赤のチャンネルを読む（MASK_CHANNEL）。範囲が無ければ全部黒（守る所が無い）。"""
import io

import numpy as np
from PIL import Image, ImageDraw


def protected_mask_png(width: int, height: int, polygons: list[list[tuple[float, float]]],
                       masks: list[bytes] = ()) -> bytes:
    """人の手の範囲を白にしたマスク。範囲は多角形（polygons）か、画素のマスク（masks：同じ大きさの PNG。白い所が範囲）。
    消しゴムで消した所は画素のマスクで来る（operations/pen_stroke_operations.py）。
    重ねるのは numpy で行う（マスクごとに絵全体へ貼り直さない）。"""
    if width <= 0 or height <= 0:
        raise ValueError(f"絵の大きさが正しくない: {width}x{height}")
    base = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(base)
    for poly in polygons:
        draw.polygon([(float(x), float(y)) for x, y in poly], fill=255)
    union = np.array(base)
    for data in masks:
        m = Image.open(io.BytesIO(data)).convert("L")
        if m.size != (width, height):
            raise ValueError(f"人の手の範囲のマスクの大きさ {m.size} が絵 {width}x{height} と違う")
        union[np.asarray(m) >= 128] = 255
    lum = Image.fromarray(union, "L")
    buf = io.BytesIO()
    Image.merge("RGB", (lum, lum, lum)).save(buf, format="PNG")
    return buf.getvalue()
