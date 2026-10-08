"""ペンの線の形と、線の消しゴム（V3細部の決めごと 10.1 のペン・消しゴム）。答えが決まる計算だけを置く。

線が正本で、層の絵は線から作った控え（operations/pen_stroke_operations.py）。
筆は今のアプリ（js/sidebar/pen/pen-tools.js）と同じ12種。eraser（消す筆）と mosaic（下をモザイクにする筆）も
線として残し、控えの絵を作るときに、その層の下の線へ順に効かせる。

線の消しゴムは3つ：
- whole：触れた線を丸ごと消す
- to_crossings：触れた所から、ほかの線と交わる所まで消す（交わりが無ければ線の端まで）
- touched：触れた所だけ消す（線は分かれる）
どれも答えは「変わった線の点」で、画素ではない。AIの絵の層を消すのは画素の消しゴム（hand_tools/pen_stroke_raster.py）。
"""

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from v3server.name_structure.item_styles import Color

Brush = Literal["pencil", "double_outline", "pattern", "vertical_lines", "horizontal_lines", "crayon", "circle", "ink",
                "marker", "spray", "mosaic", "eraser"]
# 乱れのある筆。同じ絵に描き直すため seed が要る
SEEDED_BRUSHES = {"crayon", "spray", "circle", "ink", "marker"}
# 色を持たない筆（下を消す・モザイクにする）
COLORLESS_BRUSHES = {"eraser", "mosaic"}

EraseMode = Literal["whole", "to_crossings", "touched"]

# 点：(x_mm, y_mm, 筆圧, 描き始めからの ms)
StrokePoint = tuple[float, float, float, float]


class StrokeValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brush: Brush
    points: list[StrokePoint] = Field(min_length=1)
    width_mm: float = Field(gt=0)
    color: Color | None = None
    opacity: float = Field(default=1.0, gt=0, le=1)
    seed: int | None = None
    brush_options: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check(self):
        if (self.brush in COLORLESS_BRUSHES) != (self.color is None):
            raise ValueError(f"{self.brush} は色を{'持たない' if self.brush in COLORLESS_BRUSHES else '持つ'}")
        if self.brush in SEEDED_BRUSHES and self.seed is None:
            raise ValueError(f"{self.brush} は乱れのある筆なので seed が要る")
        for _, _, p, _ in self.points:
            if not 0 <= p <= 1:
                raise ValueError(f"筆圧は 0〜1: {p}")
        times = [p[3] for p in self.points]
        if any(b < a for a, b in zip(times, times[1:], strict=False)):
            raise ValueError("点の時刻が描いた順に並んでいない")
        return self


# ---------------------------------------------------------------- 幾何


def _seg_point_dist(p, a, b) -> float:
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def _dist_to_path(p, path) -> float:
    if len(path) == 1:
        return math.hypot(p[0] - path[0][0], p[1] - path[0][1])
    return min(_seg_point_dist(p, a, b) for a, b in zip(path, path[1:], strict=False))


def resample(points: list[StrokePoint], step_mm: float) -> list[StrokePoint]:
    """点の間が step_mm 以下になるよう、間に点を足す（筆圧・時刻も間を取る）。"""
    out = [tuple(points[0])]
    for a, b in zip(points, points[1:], strict=False):
        n = max(1, math.ceil(math.hypot(b[0] - a[0], b[1] - a[1]) / step_mm))
        for i in range(1, n + 1):
            t = i / n
            out.append(tuple(a[k] + (b[k] - a[k]) * t for k in range(4)))
    return out


def touched_mask(points: list[StrokePoint], stroke_width_mm: float, eraser_path, eraser_width_mm: float) -> list[bool]:
    reach = eraser_width_mm / 2 + stroke_width_mm / 2
    return [_dist_to_path(p, eraser_path) <= reach for p in points]


def _runs(flags: list[bool], value: bool) -> list[tuple[int, int]]:
    """flags が value の並びの [始め, 終わり) の一覧。"""
    out, start = [], None
    for i, f in enumerate([*flags, not value]):
        if f == value and start is None:
            start = i
        elif f != value and start is not None:
            out.append((start, i))
            start = None
    return out


def _seg_intersect(p1, p2, q1, q2) -> bool:
    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    d1, d2 = orient(q1, q2, p1), orient(q1, q2, p2)
    d3, d4 = orient(p1, p2, q1), orient(p1, p2, q2)
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)


def crossing_indices(points: list[StrokePoint], others: list[list[StrokePoint]]) -> list[int]:
    """この線の点 i と i+1 の間でほかの線と交わる i の一覧。"""
    out = []
    for i, (a, b) in enumerate(zip(points, points[1:], strict=False)):
        if any(_seg_intersect(a, b, c, d) for o in others for c, d in zip(o, o[1:], strict=False)):
            out.append(i)
    return out


def erase(points: list[StrokePoint], stroke_width_mm: float, eraser_path: list[tuple[float, float]],
          eraser_width_mm: float, mode: EraseMode, others: list[list[StrokePoint]]) -> list[list[StrokePoint]] | None:
    """消した後に残る線の点の一覧（0本・1本・2本以上）。触れていなければ None。
    点は消しゴムの幅の 1/4 以下の間に足してから調べる（触れた所の端がずれる量はその間まで）。"""
    step = max(eraser_width_mm / 4, 1e-3)
    pts = resample(points, step)
    hit = touched_mask(pts, stroke_width_mm, eraser_path, eraser_width_mm)
    if not any(hit):
        return None
    if mode == "whole":
        return []
    if mode == "touched":
        return [pts[s:e] for s, e in _runs(hit, False)]
    # to_crossings：触れた所の前後の、いちばん近い交わりまで消す
    crosses = crossing_indices(pts, others)
    gone = [False] * len(pts)
    for s, e in _runs(hit, True):
        before = [c for c in crosses if c < s]
        after = [c for c in crosses if c >= e - 1]
        lo = before[-1] + 1 if before else 0
        hi = after[0] + 1 if after else len(pts)
        for i in range(lo, hi):
            gone[i] = True
    return [pts[s:e] for s, e in _runs(gone, False)]


def moved(points: list[StrokePoint], dx_mm: float, dy_mm: float) -> list[list[float]]:
    return [[x + dx_mm, y + dy_mm, p, t] for x, y, p, t in points]


async def refuse_stale_stroke_cache(session, image_id: str) -> None:
    """この絵を控えに持つ層の線が、控えを作った後に変わっていれば止める（AIへ渡すとき・書き出すとき）。"""
    from sqlalchemy import select

    from v3server.canonical_tables.text_and_layer_tables import PanelLayer
    from v3server.v3_error_types import Invalid

    q = select(PanelLayer).where(PanelLayer.image_id == image_id, PanelLayer.removed.is_(False))
    for layer in (await session.execute(q)).scalars():
        if layer.stroke_revision > 0 and layer.image_stroke_revision != layer.stroke_revision:
            raise Invalid(f"層 {layer.id} の絵は古い控え（線の版 {layer.image_stroke_revision}、今は {layer.stroke_revision}）。"
                          "画面で描き直して上げる")
