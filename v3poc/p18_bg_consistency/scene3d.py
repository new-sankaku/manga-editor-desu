"""箱だけで組んだ簡単な3Dの場所を、カメラの位置と向きを変えて描く（奥行きの図と線画）。
外の3Dソフトを使わず numpy の光線の当たり判定で描く。箱は軸にそろえた直方体だけ。
座標：x 右、y 上、z 奥。単位はメートルのつもり。"""
import math

import numpy as np
from PIL import Image

# 場所：名前 → 箱の並び (x0, y0, z0, x1, y1, z1)。部屋は内側から見るので、壁は薄い箱で作る
PLACES = {
    'room': {  # 教室：幅8・奥行き10・高さ3。左に窓の壁、前に黒板、机が3列×3
        'boxes': [(-4, -0.1, -1, 4, 0, 10), (-4, 3, -1, 4, 3.1, 10),                 # 床・天井
                  (-4.1, 0, -1, -4, 3, 10), (4, 0, -1, 4.1, 3, 10), (-4, 0, 10, 4, 3, 10.1),  # 左右の壁・前の壁
                  (-1.5, 0.9, 9.95, 1.5, 2.1, 10),                                     # 黒板
                  (-4, 1.0, 2, -3.95, 2.4, 4), (-4, 1.0, 5, -3.95, 2.4, 7),             # 窓
                  (3.95, 0, 8, 4, 2.1, 9),                                             # 戸
                  (-4, 0, -1.1, 4, 3, -1), (-3.5, 0, -1, 1.5, 1.8, -0.5)]               # 後ろの壁・ロッカー
                 + [(x, 0, z, x + 1.0, 0.75, z + 0.6) for x in (-2.5, -0.5, 1.5) for z in (3, 5, 7)],  # 机
        'cams': {  # 目の高さ・位置・向き（水平の角度・上下の角度）
            'front': ((0, 1.5, 0.2), 0, -5),      # 後ろから黒板を見る
            'side': ((3.3, 1.5, 3.0), -60, -5),   # 右の壁ぎわから、窓の方を斜めに見る
            'back': ((-1.0, 1.5, 9.3), 170, -8),  # 黒板の前から後ろを見る
        },
    },
    'street': {  # 街：真ん中に幅6の道、両側に高さの違う建物の箱
        'boxes': [(-40, -0.1, -5, 40, 0, 120)]
                 + [(-3 - d, 0, z, -3, h, z + 7) for z, h, d in ((0, 9, 8), (8, 14, 7), (16, 7, 9), (24, 18, 8), (32, 10, 6), (40, 12, 8), (48, 8, 7))]
                 + [(3, 0, z, 3 + d, h, z + 7) for z, h, d in ((2, 12, 7), (10, 6, 8), (18, 16, 9), (26, 9, 7), (34, 20, 8), (42, 7, 6), (50, 11, 8))]
                 + [(2.6, 0, z, 2.8, 5, z + 0.2) for z in (5, 15, 25, 35)],              # 右側の電柱
        'cams': {
            'front': ((0, 1.5, -2), 0, 2),        # 道の真ん中から奥を見る
            'side': ((-2.2, 1.5, 12), 35, 5),     # 左の歩道から、右の建物を斜めに見上げる
            'back': ((1.0, 1.5, 40), 185, 0),     # 奥から手前を振り返る
        },
    },
}


def rays(w, h, fov, yaw, pitch):
    """カメラの向きの光線（w×h×3）。fov は横の画角（度）。"""
    f = (w / 2) / math.tan(math.radians(fov) / 2)
    xs, ys = np.meshgrid(np.arange(w) - w / 2 + 0.5, h / 2 - np.arange(h) - 0.5)
    d = np.stack([xs, ys, np.full_like(xs, f)], -1)
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    d = d @ np.array([[1, 0, 0], [0, cp, sp], [0, -sp, cp]])  # 上下
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    d = d @ np.array([[cy, 0, -sy], [0, 1, 0], [sy, 0, cy]])  # 水平
    return d


def render(place, cam, w, h, fov=70):
    """奥行き（近いほど白）と、面の区切りの線画（白地に黒）を返す。"""
    boxes = np.array(PLACES[place]['boxes'], dtype=np.float64)
    pos, yaw, pitch = PLACES[place]['cams'][cam]
    o = np.array(pos, dtype=np.float64)
    d = rays(w, h, fov, yaw, pitch).reshape(-1, 3)
    inv = 1 / np.where(np.abs(d) < 1e-9, 1e-9, d)
    best = np.full(len(d), np.inf)
    face = np.full(len(d), -1)
    for i, b in enumerate(boxes):
        t0 = (b[:3] - o) * inv
        t1 = (b[3:] - o) * inv
        tmin, tmax = np.minimum(t0, t1), np.maximum(t0, t1)
        tn = tmin.max(1)
        tf = tmax.min(1)
        hit = (tn <= tf) & (tf > 0)
        tn = np.where(tn > 0, tn, tf)  # 箱の中にいるときは出口を使う
        axis = np.where(tmin.max(1) > 0, tmin.argmax(1), tmax.argmin(1))
        better = hit & (tn < best)
        best[better] = tn[better]
        face[better] = i * 6 + axis[better] * 2 + (d[better, axis[better]] > 0)
    best = best.reshape(h, w)
    face = face.reshape(h, w)
    far = np.nanpercentile(best[np.isfinite(best)], 98)
    depth = np.clip(1 - best / far, 0, 1)
    depth[~np.isfinite(best)] = 0
    # 線：面が変わる所と、奥行きが飛ぶ所
    e = np.zeros((h, w), bool)
    e[:, 1:] |= face[:, 1:] != face[:, :-1]
    e[1:, :] |= face[1:, :] != face[:-1, :]
    lb = np.log(np.where(np.isfinite(best), best, far * 4))
    e[:, 1:] |= np.abs(lb[:, 1:] - lb[:, :-1]) > 0.05
    e[1:, :] |= np.abs(lb[1:, :] - lb[:-1, :]) > 0.05
    e = e | np.roll(e, 1, 0) | np.roll(e, 1, 1)  # 2画素の太さ
    return Image.fromarray((depth * 255).astype(np.uint8)).convert('RGB'), Image.fromarray(np.where(e, 0, 255).astype(np.uint8)).convert('RGB')
