"""人の手の範囲（多角形・絵の画素の座標）から、描き直しの手順（protected_redraw_graph.py）に渡すマスクの絵を描く。
白が人の範囲、黒がそれ以外。手順は赤のチャンネルを読む（MASK_CHANNEL）。範囲が無ければ全部黒（守る所が無い）。"""
import io

from PIL import Image, ImageDraw


def protected_mask_png(width: int, height: int, polygons: list[list[tuple[float, float]]]) -> bytes:
    if width <= 0 or height <= 0:
        raise ValueError(f"絵の大きさが正しくない: {width}x{height}")
    im = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(im)
    for poly in polygons:
        draw.polygon([(float(x), float(y)) for x, y in poly], fill=(255, 255, 255))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()
