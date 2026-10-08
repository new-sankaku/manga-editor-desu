"""多角形と四角の計算（面積・重なり・中心・距離・縮める）。座標の単位は呼ぶ側が決める（ネームでは mm）。
試作 p06・p08・p14・p45・p47 にそれぞれ書いていた計算をまとめた。"""
import math
from collections.abc import Sequence

import numpy as np

Point = tuple[float, float]
Polygon = Sequence[Point]
# 四角は (左, 上, 右, 下)
Box = tuple[float, float, float, float]

# 浮動小数の計算の誤差を吸収する幅。判定の閾値ではない（閾値は呼ぶ側から渡す）
FLOAT_EPS = 1e-6

# 楕円の面積を数値で積分するときの分割数。測る精度であって、判定の閾値ではない
_ELLIPSE_STRIPS = 2048


def rect_polygon(box: Box) -> list[Point]:
    """四角を、左上から時計回りの4頂点にする。"""
    x0, y0, x1, y1 = box
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def polygon_signed_area(poly: Polygon) -> float:
    """符号付きの面積（靴ひもの公式）。y が下へ増える座標では、画面上の時計回りが正になる。"""
    s = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return s / 2


def polygon_area(poly: Polygon) -> float:
    return abs(polygon_signed_area(poly))


def polygon_centroid(poly: Polygon) -> Point:
    """面積の重心。面積が0の多角形は頂点の平均を返さず、例外にする（誤った中心を返さない）。"""
    a = polygon_signed_area(poly)
    if abs(a) < FLOAT_EPS:
        raise ValueError("面積が0の多角形には重心が無い")
    cx = cy = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        c = x0 * y1 - x1 * y0
        cx += (x0 + x1) * c
        cy += (y0 + y1) * c
    return cx / (6 * a), cy / (6 * a)


def vertex_mean(poly: Polygon) -> Point:
    """頂点の平均（試作 p45 の centroid）。縮めるときの中心に使う。"""
    return sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)


def polygon_bbox(poly: Polygon) -> Box:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def box_width(b: Box) -> float:
    return b[2] - b[0]


def box_height(b: Box) -> float:
    return b[3] - b[1]


def box_area(b: Box) -> float:
    return max(0.0, box_width(b)) * max(0.0, box_height(b))


def box_overlap_area(a: Box, b: Box) -> float:
    ix = min(a[2], b[2]) - max(a[0], b[0])
    iy = min(a[3], b[3]) - max(a[1], b[1])
    return ix * iy if ix > 0 and iy > 0 else 0.0


def box_iou(a: Box, b: Box) -> float:
    """重なり÷合わせた面積（試作 p47 の iou）。"""
    i = box_overlap_area(a, b)
    u = box_area(a) + box_area(b) - i
    return i / u if u > 0 else 0.0


def box_inside(inner: Box, outer: Box) -> bool:
    """inner が outer の中に収まるか（誤差の幅だけ許す）。"""
    return (inner[0] >= outer[0] - FLOAT_EPS and inner[1] >= outer[1] - FLOAT_EPS
            and inner[2] <= outer[2] + FLOAT_EPS and inner[3] <= outer[3] + FLOAT_EPS)


def polygon_is_convex(poly: Polygon) -> bool:
    sign = 0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        x2, y2 = poly[(i + 2) % n]
        cross = (x1 - x0) * (y2 - y1) - (y1 - y0) * (x2 - x1)
        if abs(cross) < FLOAT_EPS:
            continue
        s = 1 if cross > 0 else -1
        if sign == 0:
            sign = s
        elif s != sign:
            return False
    return True


def _clip_by_convex(subject: Polygon, clip: Polygon) -> list[Point]:
    """Sutherland–Hodgman。clip は凸でなければならない。subject は凹でも面積は正しく出る。"""
    out = list(subject)
    orient = 1 if polygon_signed_area(clip) > 0 else -1
    n = len(clip)
    for i in range(n):
        if not out:
            break
        ax, ay = clip[i]
        bx, by = clip[(i + 1) % n]

        def inside(p: Point) -> bool:
            return orient * ((bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax)) >= -FLOAT_EPS

        def cross_point(p: Point, q: Point) -> Point:
            dx, dy = q[0] - p[0], q[1] - p[1]
            den = (bx - ax) * dy - (by - ay) * dx
            t = ((bx - ax) * (ay - p[1]) - (by - ay) * (ax - p[0])) / den
            return p[0] + t * dx, p[1] + t * dy

        src, out = out, []
        for j in range(len(src)):
            cur, nxt = src[j], src[(j + 1) % len(src)]
            if inside(cur):
                out.append(cur)
                if not inside(nxt):
                    out.append(cross_point(cur, nxt))
            elif inside(nxt):
                out.append(cross_point(cur, nxt))
    return out


def polygon_overlap_area(a: Polygon, b: Polygon) -> float:
    """2つの多角形の重なりの面積。どちらか一方は凸でなければならない（両方が凹なら例外）。"""
    if polygon_is_convex(b):
        clipped = _clip_by_convex(a, b)
    elif polygon_is_convex(a):
        clipped = _clip_by_convex(b, a)
    else:
        raise ValueError("両方とも凹の多角形の重なりは計算できない")
    return polygon_area(clipped) if len(clipped) >= 3 else 0.0


def point_in_polygon(p: Point, poly: Polygon) -> bool:
    """偶奇の規則。辺の上の点はどちらにもなりうる。"""
    x, y = p
    inside = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xc = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if xc > x:
                inside = not inside
    return inside


def _segment_point_distance(p: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def _segments_cross(a: Point, b: Point, c: Point, d: Point) -> bool:
    def orient(p: Point, q: Point, r: Point) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    return o1 * o2 < 0 and o3 * o4 < 0


def polygon_distance(a: Polygon, b: Polygon) -> float:
    """2つの多角形の辺どうしの最短距離。重なっている・接している・辺が交わるときは0。"""
    na, nb = len(a), len(b)
    for i in range(na):
        for j in range(nb):
            if _segments_cross(a[i], a[(i + 1) % na], b[j], b[(j + 1) % nb]):
                return 0.0
    if point_in_polygon(a[0], b) or point_in_polygon(b[0], a):
        return 0.0
    best = math.inf
    for i in range(na):
        for j in range(nb):
            best = min(best, _segment_point_distance(a[i], b[j], b[(j + 1) % nb]),
                       _segment_point_distance(b[j], a[i], a[(i + 1) % na]))
    return best


def shrink_polygon(poly: Polygon, distance: float) -> list[Point]:
    """各頂点を、頂点の平均へ向かって distance だけ寄せる（試作 p45 の shrink）。
    隣のコマとの隙間を絵に見せるための近似で、辺が平行に distance 下がるわけではない。"""
    cx, cy = vertex_mean(poly)
    out = []
    for x, y in poly:
        dx, dy = x - cx, y - cy
        d = math.hypot(dx, dy)
        if d == 0:
            raise ValueError("頂点が中心と重なっているので縮められない")
        out.append((x - dx / d * distance, y - dy / d * distance))
    return out


def ellipse_box_coverage(ellipse_box: Box, target: Box) -> float:
    """四角 ellipse_box に内接する楕円が、四角 target の面積の何割を覆うか（0〜1）。
    試作 p47 では楕円を画素に塗って数えた。ここでは横を細かく分けて縦の長さを足す。"""
    t_area = box_area(target)
    if t_area <= 0:
        raise ValueError("覆われる側の四角の面積が0")
    ex0, ey0, ex1, ey1 = ellipse_box
    cx, cy = (ex0 + ex1) / 2, (ey0 + ey1) / 2
    rx, ry = (ex1 - ex0) / 2, (ey1 - ey0) / 2
    x0, x1 = max(target[0], ex0), min(target[2], ex1)
    if rx <= 0 or ry <= 0 or x1 <= x0:
        return 0.0
    edges = np.linspace(x0, x1, _ELLIPSE_STRIPS + 1)
    xs = (edges[:-1] + edges[1:]) / 2
    half = ry * np.sqrt(np.clip(1 - ((xs - cx) / rx) ** 2, 0, None))
    lo = np.maximum(cy - half, target[1])
    hi = np.minimum(cy + half, target[3])
    covered = float(np.clip(hi - lo, 0, None).sum() * (x1 - x0) / _ELLIPSE_STRIPS)
    return min(1.0, covered / t_area)


def ellipse_overlap_area(a: Box, b: Box) -> float:
    """2つの四角に内接する楕円どうしの重なりの面積。横を細かく分けて縦の重なりを足す。"""
    x0, x1 = max(a[0], b[0]), min(a[2], b[2])
    if x1 <= x0:
        return 0.0
    edges = np.linspace(x0, x1, _ELLIPSE_STRIPS + 1)
    xs = (edges[:-1] + edges[1:]) / 2

    def span(e: Box) -> tuple[np.ndarray, np.ndarray]:
        cx, cy = (e[0] + e[2]) / 2, (e[1] + e[3]) / 2
        rx, ry = (e[2] - e[0]) / 2, (e[3] - e[1]) / 2
        h = ry * np.sqrt(np.clip(1 - ((xs - cx) / rx) ** 2, 0, None))
        return cy - h, cy + h

    alo, ahi = span(a)
    blo, bhi = span(b)
    return float(np.clip(np.minimum(ahi, bhi) - np.maximum(alo, blo), 0, None).sum() * (x1 - x0) / _ELLIPSE_STRIPS)
