"""fabric.js 5.3 の物（今のアプリのキャンバスの JSON）の形と位置を、キャンバスの画素の座標に直す。

fabric.js の決まり（fabric 5.3.0 の calcTransformMatrix・translateToCenterPoint・_getTransformedDimensions に合わせた）
- 物の行列 = 真ん中へ動かす・回す（angle、時計回り）・傾ける（skewX・skewY）・拡大する（scaleX・scaleY と flipX・flipY）
- left・top は originX・originY の点。真ん中は、その点から、拡大した大きさ（線の太さを含む）の半分だけ回した向きへずらした所
  - strokeUniform のとき：大きさ = width × scaleX + strokeWidth。そうでないとき：(width + strokeWidth) × scaleX
- 多角形（polygon）の点と線（path）の点は、点の外接の箱の真ん中（pathOffset）を原点にした座標に直してから行列を当てる
- グループの中の物の left・top は、グループの真ん中を原点にした座標。グループの行列を外から当てる

傾いた物の大きさは傾きを入れずに出す（fabric は傾きを入れた外接の箱から真ん中を出す）。傾いた物は位置が少しずれる（未検証）。
線の曲線（Q・C）は点の列に直す。外接の箱は曲線の点を細かく取って出すので、fabric の計算（曲線の極値）と少し違う。
"""

import math
import re
from typing import Any

import numpy as np
from PIL import ImageColor

Point = tuple[float, float]

_ORIGIN = {"left": -0.5, "top": -0.5, "center": 0.0, "right": 0.5, "bottom": 0.5}
# 曲線1本を何本の線に分けるか
CURVE_STEPS = 16


class GeometryError(ValueError):
    pass


def _num(obj: dict[str, Any], key: str, default: float) -> float:
    v = obj.get(key)
    return float(v) if isinstance(v, (int, float)) else default


def _origin(obj: dict[str, Any], key: str) -> float:
    v = obj.get(key, "left" if key == "originX" else "top")
    if isinstance(v, (int, float)):
        return float(v) - 0.5
    if v not in _ORIGIN:
        raise GeometryError(f"知らない {key}: {v}")
    return _ORIGIN[v]


def scaled_size(obj: dict[str, Any]) -> tuple[float, float]:
    """拡大した後の大きさ（線の太さを含む、傾きは入れない）。"""
    w, h = _num(obj, "width", 0.0), _num(obj, "height", 0.0)
    sx, sy = abs(_num(obj, "scaleX", 1.0)), abs(_num(obj, "scaleY", 1.0))
    sw = _num(obj, "strokeWidth", 0.0)
    if obj.get("strokeUniform"):
        return w * sx + sw, h * sy + sw
    return (w + sw) * sx, (h + sw) * sy


def center_of(obj: dict[str, Any]) -> Point:
    """物の真ん中（親の座標。グループの中の物はグループの真ん中が原点）。"""
    w, h = scaled_size(obj)
    ox, oy = _origin(obj, "originX"), _origin(obj, "originY")
    dx, dy = -ox * w, -oy * h
    a = math.radians(_num(obj, "angle", 0.0))
    return (_num(obj, "left", 0.0) + dx * math.cos(a) - dy * math.sin(a),
            _num(obj, "top", 0.0) + dx * math.sin(a) + dy * math.cos(a))


def object_matrix(obj: dict[str, Any]) -> np.ndarray:
    """物の真ん中を原点にした（拡大する前の）座標 → 親の座標 の 3x3 の行列。"""
    cx, cy = center_of(obj)
    a = math.radians(_num(obj, "angle", 0.0))
    sx = _num(obj, "scaleX", 1.0) * (-1 if obj.get("flipX") else 1)
    sy = _num(obj, "scaleY", 1.0) * (-1 if obj.get("flipY") else 1)
    kx, ky = math.tan(math.radians(_num(obj, "skewX", 0.0))), math.tan(math.radians(_num(obj, "skewY", 0.0)))
    t = np.array([[1, 0, cx], [0, 1, cy], [0, 0, 1]], float)
    r = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]], float)
    skew_x = np.array([[1, kx, 0], [0, 1, 0], [0, 0, 1]], float)
    skew_y = np.array([[1, 0, 0], [ky, 1, 0], [0, 0, 1]], float)
    s = np.diag([sx, sy, 1.0])
    return t @ r @ s @ skew_x @ skew_y


def apply(m: np.ndarray, pts: list[Point]) -> list[Point]:
    arr = np.array([[x, y, 1.0] for x, y in pts], float).T
    out = m @ arr
    return [(float(x), float(y)) for x, y in zip(out[0], out[1], strict=True)]


def _centered(pts: list[Point]) -> list[Point]:
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    return [(x - cx, y - cy) for x, y in pts]


def polygon_points(obj: dict[str, Any]) -> list[Point]:
    pts = obj.get("points")
    if not isinstance(pts, list) or len(pts) < 3:
        raise GeometryError("多角形の点が3つ無い")
    return [(float(p["x"]), float(p["y"])) for p in pts]


def rect_corners(obj: dict[str, Any]) -> list[Point]:
    """物の箱の4隅（物の真ん中が原点、拡大する前）。"""
    w, h = _num(obj, "width", 0.0) / 2, _num(obj, "height", 0.0) / 2
    return [(-w, -h), (w, -h), (w, h), (-w, h)]


def path_points(path: list[Any]) -> list[list[Point]]:
    """fabric の path（["M",x,y]・["L",x,y]・["Q",..]・["C",..]・["Z"]、どれも絶対の座標）を、輪ごとの点の列にする。"""
    rings: list[list[Point]] = []
    cur: list[Point] = []
    pos: Point = (0.0, 0.0)
    start: Point = (0.0, 0.0)
    for cmd in path:
        if not isinstance(cmd, list) or not cmd:
            raise GeometryError(f"線の命令の形が正しくない: {cmd}")
        op, args = cmd[0], [float(v) for v in cmd[1:]]
        if op == "M":
            if len(cur) > 1:
                rings.append(cur)
            pos = start = (args[0], args[1])
            cur = [pos]
        elif op == "L":
            pos = (args[0], args[1])
            cur.append(pos)
        elif op == "Q":
            (x1, y1, x2, y2) = args
            p0 = pos
            for i in range(1, CURVE_STEPS + 1):
                t = i / CURVE_STEPS
                cur.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * x1 + t * t * x2,
                            (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * y1 + t * t * y2))
            pos = (x2, y2)
        elif op == "C":
            (x1, y1, x2, y2, x3, y3) = args
            p0 = pos
            for i in range(1, CURVE_STEPS + 1):
                t = i / CURVE_STEPS
                u = 1 - t
                cur.append((u ** 3 * p0[0] + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t ** 3 * x3,
                            u ** 3 * p0[1] + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t ** 3 * y3))
            pos = (x3, y3)
        elif op in ("Z", "z"):
            pos = start
            if len(cur) > 1:
                rings.append(cur)
            cur = []
        else:
            # fabric 5 は読み込むときに H・V・A などを M・L・Q・C・Z に直す。それ以外が来たら止める
            raise GeometryError(f"読めない線の命令: {op}")
    if len(cur) > 1:
        rings.append(cur)
    return rings


def path_center_offset(rings: list[list[Point]]) -> Point:
    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def object_polygon_px(obj: dict[str, Any], parent: np.ndarray | None = None) -> list[Point]:
    """物の外形（キャンバスの画素の座標）。多角形は点、ほかは箱の4隅。"""
    m = object_matrix(obj) if parent is None else parent @ object_matrix(obj)
    if obj.get("type") == "polygon":
        return apply(m, _centered(polygon_points(obj)))
    return apply(m, rect_corners(obj))


def path_rings_px(obj: dict[str, Any], parent: np.ndarray | None = None) -> list[list[Point]]:
    m = object_matrix(obj) if parent is None else parent @ object_matrix(obj)
    rings = path_points(obj.get("path") or [])
    if not rings:
        return []
    ox, oy = path_center_offset(rings)
    return [apply(m, [(x - ox, y - oy) for x, y in r]) for r in rings]


def polygon_area(pts: list[Point]) -> float:
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1], strict=True))) / 2


def point_in_polygon(p: Point, poly: list[Point]) -> bool:
    x, y = p
    inside = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1], strict=True):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


_RGBA = re.compile(r"^rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([0-9.]+)\s*\)$")


def css_color(v: Any) -> tuple[str, float] | None:
    """CSS の色を (#RRGGBB, 不透明度) にする。無い色（None・空・transparent）は None。読めない色は止める。"""
    if v is None or v == "" or v == "transparent":
        return None
    if not isinstance(v, str):
        raise GeometryError(f"色の形でない: {v!r}")
    m = _RGBA.match(v.strip())
    if m:
        r, g, b, a = int(m[1]), int(m[2]), int(m[3]), float(m[4])
        return f"#{r:02x}{g:02x}{b:02x}", a
    try:
        rgb = ImageColor.getrgb(v)
    except ValueError as e:
        raise GeometryError(f"読めない色: {v}") from e
    return "#{:02x}{:02x}{:02x}".format(*rgb[:3]), (rgb[3] / 255 if len(rgb) == 4 else 1.0)
