"""消しゴムの保存と人の手の範囲のマスクの時間を、4960×7016 の絵で測る（llm_doc/V3画像生成の機能と画面.md 6.6 の数字）。
大きな絵を作るので、ふだんの試験からは外す。V3_PERF=1 で流す（-s を付けると時間が出る）。
時間は機械で変わるので、合否は付けない（出た物の形だけ確かめる）。"""
import io
import os
import random
import time

import pytest
from PIL import Image, ImageDraw

from v3server.comfy_graphs.protected_region_mask import protected_mask_png
from v3server.hand_tools.pen_stroke_raster import PixelEraserStroke, erase_pixels

pytestmark = [pytest.mark.perf,
              pytest.mark.skipif(os.environ.get("V3_PERF") != "1", reason="時間を測る試験。V3_PERF=1 で流す")]

W, H = 4960, 7016


def _line_art() -> bytes:
    """線画らしい絵：白地に黒い線を 3,000 本、薄い灰色の四角を 400 個。"""
    rng = random.Random(1)
    im = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    d = ImageDraw.Draw(im)
    for _ in range(400):
        x, y = rng.randrange(W), rng.randrange(H)
        d.rectangle((x, y, x + rng.randrange(50, 600), y + rng.randrange(50, 600)), fill=(200, 200, 200, 255))
    for _ in range(3000):
        d.line([(rng.randrange(W), rng.randrange(H)) for _ in range(2)], fill=(0, 0, 0, 255), width=rng.randrange(2, 8))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _timed(fn, *args):
    t = time.perf_counter()
    out = fn(*args)
    return out, time.perf_counter() - t


def test_消しゴム1本の保存():
    base = _line_art()
    stroke = [PixelEraserStroke(points=[(1000 + i * 8, 2000 + (i % 7) * 3) for i in range(120)], width_px=40)]
    for _ in range(3):
        (png, mask), sec = _timed(erase_pixels, base, stroke)
        print(f"erase_pixels {sec:.2f}s")
    assert Image.open(io.BytesIO(png)).size == (W, H) and Image.open(io.BytesIO(mask)).size == (W, H)


def test_人の手の範囲のマスクを重ねる():
    rng = random.Random(2)
    masks = []
    for _ in range(20):
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).line([(rng.randrange(W), rng.randrange(H)) for _ in range(30)], fill=255, width=30)
        buf = io.BytesIO()
        m.save(buf, format="PNG")
        masks.append(buf.getvalue())
    for n in (1, 10, 20):
        _, sec = _timed(protected_mask_png, W, H, [], masks[:n])
        print(f"protected_mask_png {n} {sec:.2f}s")
    # 控え（前の 19 個を重ねた物）に新しい範囲を1つ重ねる（generation_queue/protected_mask_cache.py がする事）
    cached = protected_mask_png(W, H, [], masks[:19])
    out, sec = _timed(protected_mask_png, W, H, [], [cached, masks[19]])
    print(f"控え + 新しい範囲1つ {sec:.2f}s")
    assert out == protected_mask_png(W, H, [], masks)
