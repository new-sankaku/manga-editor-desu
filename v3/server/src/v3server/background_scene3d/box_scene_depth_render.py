"""箱と板だけで組んだ場所を、カメラの位置と向きから描く（奥行きの図と線画）。移す元は試作 p18 `scene3d.py`。

外の3Dソフトを使わず、numpy の光線の当たり判定で描く。箱は軸にそろえた直方体だけ（板は薄い箱）。
座標：x 右、y 上、z 奥。単位はメートルのつもり。
描いた図は `comfy_graphs/controlnet_nodes.py` の奥行き・線画の制御に渡す。

試作 p18 で分かったこと：
- 奥行きか線画を渡すと、壁・床・天井の境目、机の数と位置、道の向き、建物の並びが、向きを変えても揃った。
- 壁に何を描くかは揃わない（ロッカーの壁にも窓の壁にも黒板が描かれた）。箱が面に何があるかを持たないためと考えるが未検証。
- 箱の形がそのまま写る（机が脚のない箱のまま描かれた）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image

# 奥行きの図で白から黒へ変える遠さ：当たった距離のこの百分位を一番遠い所とする
FAR_PERCENTILE = 98
# 何にも当たらない光線の、線を引くときの距離（一番遠い所の何倍か）
MISS_DISTANCE_FACTOR = 4
# 0 で割らないための小さな値
EPS = 1e-9


@dataclass(frozen=True)
class Box:
    """軸にそろえた直方体。(x0, y0, z0) が小さい角、(x1, y1, z1) が大きい角。"""

    x0: float
    y0: float
    z0: float
    x1: float
    y1: float
    z1: float


@dataclass(frozen=True)
class Camera:
    """カメラ。position は目の位置、yaw_degrees は水平の向き（0 で奥 +z、正で右回り）、pitch_degrees は上下（正で下を向く。試作 p18 の注記の「見上げる」とは逆なので、試験で確かめた）。

    fov_degrees は横の画角。
    """

    position: tuple[float, float, float]
    yaw_degrees: float
    pitch_degrees: float
    fov_degrees: float


@dataclass(frozen=True)
class LineSettings:
    """線画の引き方。

    depth_jump_log：隣の画素との距離の対数の差がこれを超えたら、奥行きが飛んだとみなして線を引く（試作は 0.05）。
    thickness_px：線の太さ（試作は 2）。
    """

    depth_jump_log: float
    thickness_px: int


@dataclass(frozen=True)
class DepthAndLine:
    """奥行きの図（近いほど白）と線画（白地に黒い線）。どちらも RGB。"""

    depth: Image.Image
    line: Image.Image


def camera_rays(width: int, height: int, camera: Camera) -> np.ndarray:
    """画素ごとの光線の向き（height×width×3、長さ1）。"""
    f = (width / 2) / math.tan(math.radians(camera.fov_degrees) / 2)
    xs, ys = np.meshgrid(np.arange(width) - width / 2 + 0.5, height / 2 - np.arange(height) - 0.5)
    d = np.stack([xs, ys, np.full_like(xs, f)], -1)
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    cp, sp = math.cos(math.radians(camera.pitch_degrees)), math.sin(math.radians(camera.pitch_degrees))
    d = d @ np.array([[1, 0, 0], [0, cp, sp], [0, -sp, cp]])  # 上下
    cy, sy = math.cos(math.radians(camera.yaw_degrees)), math.sin(math.radians(camera.yaw_degrees))
    d = d @ np.array([[cy, 0, -sy], [0, 1, 0], [sy, 0, cy]])  # 水平
    return d


def _hit_boxes(boxes: list[Box], origin: np.ndarray, d: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """光線ごとの一番近い当たりの距離（当たらなければ inf）と、当たった面の番号（当たらなければ -1）。"""
    arr = np.array([(b.x0, b.y0, b.z0, b.x1, b.y1, b.z1) for b in boxes], dtype=np.float64)
    inv = 1 / np.where(np.abs(d) < EPS, EPS, d)
    best = np.full(len(d), np.inf)
    face = np.full(len(d), -1)
    for i, b in enumerate(arr):
        t0 = (b[:3] - origin) * inv
        t1 = (b[3:] - origin) * inv
        tmin, tmax = np.minimum(t0, t1), np.maximum(t0, t1)
        t_near = tmin.max(1)
        t_far = tmax.min(1)
        hit = (t_near <= t_far) & (t_far > 0)
        t_hit = np.where(t_near > 0, t_near, t_far)  # 箱の中にいるとき（部屋の中から壁を見る）は出口を使う
        axis = np.where(t_near > 0, tmin.argmax(1), tmax.argmin(1))
        better = hit & (t_hit < best)
        best[better] = t_hit[better]
        # 面の番号：箱ごとに6面（軸×向き）
        face[better] = i * 6 + axis[better] * 2 + (d[better, axis[better]] > 0)
    return best, face


def _thicken(edge: np.ndarray, thickness_px: int) -> np.ndarray:
    """線を右と下へ thickness_px 画素の太さにする（端で反対側へ回り込まない）。"""
    out = edge.copy()
    for k in range(1, thickness_px):
        out[k:, :] |= edge[:-k, :]
        out[:, k:] |= edge[:, :-k]
    return out


def render_depth_and_line(boxes: list[Box], camera: Camera, width: int, height: int, line: LineSettings) -> DepthAndLine:
    """箱の並びをカメラから描き、奥行きの図と線画を返す。

    線は、当たった面が変わる所と、奥行きが飛ぶ所に引く。
    """
    if not boxes:
        raise ValueError('箱が1つもありません')
    if line.thickness_px < 1:
        raise ValueError('線の太さは1画素以上にしてください')
    d = camera_rays(width, height, camera).reshape(-1, 3)
    best, face = _hit_boxes(boxes, np.array(camera.position, dtype=np.float64), d)
    best = best.reshape(height, width)
    face = face.reshape(height, width)
    finite = np.isfinite(best)
    if not finite.any():
        raise ValueError('カメラから箱が1つも見えません')
    far = np.percentile(best[finite], FAR_PERCENTILE)
    depth = np.clip(1 - best / far, 0, 1)
    depth[~finite] = 0

    e = np.zeros((height, width), bool)
    e[:, 1:] |= face[:, 1:] != face[:, :-1]
    e[1:, :] |= face[1:, :] != face[:-1, :]
    lb = np.log(np.where(finite, best, far * MISS_DISTANCE_FACTOR))
    e[:, 1:] |= np.abs(lb[:, 1:] - lb[:, :-1]) > line.depth_jump_log
    e[1:, :] |= np.abs(lb[1:, :] - lb[:-1, :]) > line.depth_jump_log
    e = _thicken(e, line.thickness_px)

    depth_img = Image.fromarray((depth * 255).astype(np.uint8)).convert('RGB')
    line_img = Image.fromarray(np.where(e, 0, 255).astype(np.uint8)).convert('RGB')
    return DepthAndLine(depth_img, line_img)
