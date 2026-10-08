"""コマの中の人物の枠の位置と大きさに、骨格の図（OpenPose の COCO18 の形）を描く。

移す元は試作 p14 `fig_px`・`pose_img`。描いた図は `controlnet_nodes.py` の骨格の制御に渡す。
試作で確かめた姿勢は立ち姿だけ。座る・走るなどの姿勢は未検証。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image, ImageDraw

# COCO18 の関節。立ち姿を 0〜1 の枠に正規化したもの（試作 p08・p14 と同じ形）
STANDING_KEYPOINTS = [
    (0.50, 0.05), (0.50, 0.20), (0.22, 0.21), (0.12, 0.35), (0.08, 0.49), (0.78, 0.21), (0.88, 0.35), (0.92, 0.49),
    (0.33, 0.53), (0.28, 0.76), (0.25, 0.97), (0.68, 0.53), (0.72, 0.76), (0.75, 0.97),
    (0.44, 0.04), (0.56, 0.04), (0.36, 0.05), (0.64, 0.05),
]
LIMBS = [(1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7), (1, 8), (8, 9), (9, 10), (1, 11), (11, 12), (12, 13),
         (1, 0), (0, 14), (14, 16), (0, 15), (15, 17)]
# OpenPose の図の色（関節ごと。骨は同じ色を6割の明るさで塗る）
COLORS = [(255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0), (85, 255, 0), (0, 255, 0),
          (0, 255, 85), (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255), (0, 0, 255), (85, 0, 255),
          (170, 0, 255), (255, 0, 255), (255, 0, 170), (255, 0, 85)]
LIMB_BRIGHTNESS = 0.6
# 立ち姿の肩幅と腕の広がり（人物の枠の高さに対する割合）
STANDING_WIDTH_RATIO = 0.27
# 線の太さ：人物の高さに対する割合と、最小の画素。xinsir は太い線で学習している（配布元の説明）
LINE_WIDTH_RATIO = 0.018
LINE_WIDTH_MIN_PX = 4


@dataclass(frozen=True)
class FigureBox:
    """コマに対する人物の枠（0〜1 の割合）。x は右へ、y は下へ。"""

    x0: float
    y0: float
    x1: float
    y1: float


def figure_box_pixels(width: int, height: int, box: FigureBox) -> tuple[int, int, int, int]:
    """割合の枠を、生成する絵の画素の枠 (x0, y0, x1, y1) にする。"""
    return round(box.x0 * width), round(box.y0 * height), round(box.x1 * width), round(box.y1 * height)


def draw_standing_pose(width: int, height: int, box: FigureBox) -> Image.Image:
    """黒地に、人物の枠の高さに合わせた立ち姿の骨格を描く（RGB）。

    枠の横幅は使わず、高さから肩幅を決めて枠の左右の真ん中に立たせる。
    試作 p14：骨格を渡すと、言葉だけでは真ん中に立つ人物が、横長・標準のコマでも枠の位置に来た
    （枠と検出した人物の重なり IoU 約0.72〜0.81）。
    """
    x0, y0, x1, y1 = figure_box_pixels(width, height, box)
    fh = y1 - y0
    if fh <= 0 or x1 <= x0:
        raise ValueError(f'人物の枠が空です: {box}')
    fw = fh * STANDING_WIDTH_RATIO
    cx = (x0 + x1) / 2
    pts = [(cx + (nx - 0.5) * fw, y0 + ny * fh) for nx, ny in STANDING_KEYPOINTS]
    im = Image.new('RGB', (width, height), 'black')
    d = ImageDraw.Draw(im)
    wd = max(LINE_WIDTH_MIN_PX, fh * LINE_WIDTH_RATIO)
    for i, (a, b) in enumerate(LIMBS):
        (xa, ya), (xb, yb) = pts[a], pts[b]
        ang = math.atan2(yb - ya, xb - xa)
        s, c = math.sin(ang) * wd, math.cos(ang) * wd
        color = tuple(int(v * LIMB_BRIGHTNESS) for v in COLORS[i])
        d.polygon([(xa + s, ya - c), (xb + s, yb - c), (xb - s, yb + c), (xa - s, ya + c)], fill=color)
    for i, (x, y) in enumerate(pts):
        d.ellipse((x - wd, y - wd, x + wd, y + wd), fill=COLORS[i])
    return im
