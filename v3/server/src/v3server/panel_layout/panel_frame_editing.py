"""コマ枠を分ける・合わせる・ばらばらに割る・図形のコマを作る計算（V3細部の決めごと 10.1 のナイフとコマ枠）。

答えが決まる計算だけを置く。正本を変えるのは operations/panel_frame_operations.py。
座標は基本枠の mm（x は右、y は下へ増える）。

- 分ける：押した点を通る1本の線で、凸の枠を2つにする。間の幅（gap）の半分ずつを両側から削る。
  凹んだ枠（星・ハートなど）は、1本の線で2つにならないことがあるので切らない
- 細すぎるか：分けた後の形の「最も狭い幅」（凸の形の、どの辺に平行に挟んでも測れる最小の幅）で決める
- 合わせる：2つの頂点を全部包む凸の形にする。隣り合うか（間が gap 以下か）は呼ぶ側が確かめる
"""

import math
import random
from typing import Literal

from v3server.panel_layout.panel_geometry import (
    polygon_area,
    polygon_centroid,
    polygon_distance,
    polygon_is_convex,
)

Point = tuple[float, float]

# 計算の誤差の許し（mm）。見た目の閾値ではない
EPS = 1e-6


class FrameEditError(ValueError):
    """枠をその形に変えられない（線が枠を横切らない・細すぎる・凹んでいる など）。"""


def line_normal(direction: Literal["horizontal", "vertical", "slanted"], angle_deg: float | None) -> Point:
    """切る線に直角な単位の向き。横の線は (0,1)、縦の線は (1,0)。斜めは線の角度（横から時計回り）で決める。"""
    if direction == "horizontal":
        return (0.0, 1.0)
    if direction == "vertical":
        return (1.0, 0.0)
    if angle_deg is None:
        raise FrameEditError("斜めに切るときは角度が要る")
    a = math.radians(angle_deg)
    return (-math.sin(a), math.cos(a))


def _clip_half_plane(poly: list[Point], n: Point, c: float) -> list[Point]:
    """n·p >= c の側だけを残す（凸の形なら答えも凸）。"""
    out: list[Point] = []
    m = len(poly)
    for i in range(m):
        p, q = poly[i], poly[(i + 1) % m]
        dp = n[0] * p[0] + n[1] * p[1] - c
        dq = n[0] * q[0] + n[1] * q[1] - c
        if dp >= 0:
            out.append(p)
        if (dp >= 0) != (dq >= 0):
            t = dp / (dp - dq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    # 続けて同じ点が並んだら1つにする
    cleaned: list[Point] = []
    for p in out:
        if not cleaned or math.dist(p, cleaned[-1]) > EPS:
            cleaned.append(p)
    if len(cleaned) > 1 and math.dist(cleaned[0], cleaned[-1]) <= EPS:
        cleaned.pop()
    return cleaned


def min_width(poly: list[Point]) -> float:
    """凸の形の最も狭い幅。"""
    best = math.inf
    m = len(poly)
    for i in range(m):
        p, q = poly[i], poly[(i + 1) % m]
        L = math.dist(p, q)
        if L <= EPS:
            continue
        far = max(abs((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])) / L for r in poly)
        best = min(best, far)
    return best


def split_polygon(poly: list[Point], through: Point, normal: Point, gap_mm: float, min_width_mm: float
                  ) -> tuple[list[Point], list[Point]]:
    """(線の n の向きの側, 反対の側) を返す。どちらかが無い・細すぎるなら FrameEditError。"""
    if not polygon_is_convex(poly):
        raise FrameEditError("凹んだ枠は1本の線で2つに分けられないことがあるので切らない")
    c = normal[0] * through[0] + normal[1] * through[1]
    a = _clip_half_plane(poly, normal, c + gap_mm / 2)
    b = _clip_half_plane(poly, (-normal[0], -normal[1]), -(c - gap_mm / 2))
    if len(a) < 3 or len(b) < 3 or polygon_area(a) <= EPS or polygon_area(b) <= EPS:
        raise FrameEditError("切る線が枠を横切っていない（または間の幅が枠より広い）")
    for side in (a, b):
        w = min_width(side)
        if w < min_width_mm:
            raise FrameEditError(f"分けた形の幅 {w:.1f}mm が、コマの最小の大きさ {min_width_mm}mm より細い")
    return a, b


def reading_first(a: list[Point], b: list[Point], reading_direction: Literal["rtl", "ltr"]) -> int:
    """読む順で先に来る方（0 なら a、1 なら b）。上下に並べば上が先、左右に並べば読む向きの始めの側が先。"""
    (ax, ay), (bx, by) = polygon_centroid(a), polygon_centroid(b)
    if abs(ay - by) >= abs(ax - bx):
        return 0 if ay < by else 1
    right_first = reading_direction == "rtl"
    return 0 if (ax > bx) == right_first else 1


def convex_hull(points: list[Point]) -> list[Point]:
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[Point] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[Point] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def are_adjacent(a: list[Point], b: list[Point], max_gap_mm: float) -> bool:
    return polygon_distance(a, b) <= max_gap_mm + EPS


def merged_polygon(a: list[Point], b: list[Point]) -> list[Point]:
    return convex_hull(list(a) + list(b))


# ---------------------------------------------------------------- ばらばらに割る（今のアプリ js/panel/random-cut.js）


def random_split(poly: list[Point], horizontal_cuts: int, vertical_cuts: int, gap_x_mm: float, gap_y_mm: float,
                 min_width_mm: float, seed: int, attempts_per_cut: int,
                 reading_direction: Literal["rtl", "ltr"]) -> list[list[Point]]:
    """横の線で horizontal_cuts 回、できた段ごとに縦の線で vertical_cuts 回、ランダムな位置で切る。
    同じ seed なら同じ割りになる。読む順（上の段から、段の中は読む向きの始めから）に並べて返す。
    どの切り方も細すぎて切れなければ FrameEditError。"""
    rng = random.Random(seed)

    def cut_once(piece: list[Point], direction: str) -> tuple[list[Point], list[Point]]:
        xs, ys = [p[0] for p in piece], [p[1] for p in piece]
        n = line_normal(direction, None)
        gap = gap_y_mm if direction == "horizontal" else gap_x_mm
        last: FrameEditError | None = None
        for _ in range(attempts_per_cut):
            through = (rng.uniform(min(xs), max(xs)), rng.uniform(min(ys), max(ys)))
            try:
                return split_polygon(piece, through, n, gap, min_width_mm)
            except FrameEditError as e:
                last = e
        raise FrameEditError(f"{attempts_per_cut} 回試しても切れなかった: {last}")

    rows = [poly]
    for _ in range(horizontal_cuts):
        rows.sort(key=polygon_area)
        a, b = cut_once(rows.pop(), "horizontal")
        rows += [a, b]
    rows.sort(key=lambda r: polygon_centroid(r)[1])
    out: list[list[Point]] = []
    for row in rows:
        cells = [row]
        for _ in range(vertical_cuts):
            cells.sort(key=polygon_area)
            a, b = cut_once(cells.pop(), "vertical")
            cells += [a, b]
        cells.sort(key=lambda c: polygon_centroid(c)[0], reverse=reading_direction == "rtl")
        out += cells
    return out


# ---------------------------------------------------------------- 図形のコマ（今のアプリ js/sidebar/panel/panel-template.js の形）

# 丸・楕円を多角形で持つときの頂点の数（形の細かさ。閾値ではない）
ROUND_VERTICES = 72

FrameShape = Literal["rect", "triangle", "pentagon", "hexagon", "rhombus", "trapezoid", "ellipse", "star", "heart"]


def shape_polygon(shape: FrameShape, box: tuple[float, float, float, float]) -> list[Point]:
    x0, y0, x1, y1 = box
    if x1 <= x0 or y1 <= y0:
        raise FrameEditError(f"図形の箱が正しくない: {box}")
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2

    def regular(n: int, start_deg: float = -90) -> list[Point]:
        return [(cx + rx * math.cos(math.radians(start_deg + 360 * i / n)),
                 cy + ry * math.sin(math.radians(start_deg + 360 * i / n))) for i in range(n)]

    if shape == "rect":
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if shape == "triangle":
        return [(cx, y0), (x1, y1), (x0, y1)]
    if shape == "pentagon":
        return regular(5)
    if shape == "hexagon":
        return regular(6, 0)
    if shape == "rhombus":
        return [(cx, y0), (x1, cy), (cx, y1), (x0, cy)]
    if shape == "trapezoid":
        inset = (x1 - x0) / 4
        return [(x0 + inset, y0), (x1 - inset, y0), (x1, y1), (x0, y1)]
    if shape == "ellipse":
        return regular(ROUND_VERTICES)
    if shape == "star":
        pts = []
        for i in range(10):
            r = 1.0 if i % 2 == 0 else 0.4
            a = math.radians(-90 + 36 * i)
            pts.append((cx + rx * r * math.cos(a), cy + ry * r * math.sin(a)))
        return pts
    if shape == "heart":
        pts = []
        for i in range(ROUND_VERTICES):
            t = 2 * math.pi * i / ROUND_VERTICES
            hx = 16 * math.sin(t) ** 3
            hy = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
            pts.append((cx + rx * hx / 16, cy + ry * (hy + 2.5) / 15))
        return pts
    raise FrameEditError(f"知らない形: {shape}")
