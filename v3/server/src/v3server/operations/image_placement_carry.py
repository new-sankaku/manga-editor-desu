"""絵を別の版に替えるとき（候補を採る・前の版に戻す）、置き場（ImagePlacement）を新しい版へ引き継ぐ計算。正本は触らない。

版どうしの画素の対応（Geometry：新しい画素 = 元の画素 × scale + offset）は、生成した絵の details.geometry に書いてある
（generation_queue/service_call_activity.py）。書いていない版は、前の版と同じ大きさなら画素がそろっているとみなす
（人の手の範囲を前の版から引き継ぐのと同じ決まり。input_image_preparation.protected_regions_for）。大きさが違えば対応は分からない。

引き継ぎ方
- aligned：対応が分かる。今の切り抜きを新しい版の画素へ移す。今の切り抜きが絵の端まで使っていた辺は、新しい版の端まで広げ、
  置き場（mm）も同じ比で広げる（描き足した所が見える）。新しい版の外へ出る所は切り詰め、置き場も同じだけ縮める。
  見えていた所は、ページの上で同じ位置に残る。回転・傾き・反転のある置き場は、置き場の箱を変えると回る中心が動くので、
  広げない（切り詰めだけ）
- cover：対応が分からない、または今は絵が無い。絵の全体を、コマの枠の外接する四角を覆う大きさで真ん中に置く
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from v3server.name_structure.image_placement import ImagePlacement
from v3server.v3_error_types import Invalid

EDGE_TOLERANCE_PX = 0.5


@dataclass(frozen=True)
class Geometry:
    sx: float
    sy: float
    ox: float
    oy: float

    @staticmethod
    def identity() -> Geometry:
        return Geometry(1, 1, 0, 0)

    @staticmethod
    def from_details(g: dict[str, Any]) -> Geometry:
        return Geometry(float(g["scale"][0]), float(g["scale"][1]), float(g["offset"][0]), float(g["offset"][1]))

    def then(self, other: Geometry) -> Geometry:
        """self の後に other を当てる。"""
        return Geometry(self.sx * other.sx, self.sy * other.sy, self.ox * other.sx + other.ox,
                        self.oy * other.sy + other.oy)

    def inverse(self) -> Geometry:
        return Geometry(1 / self.sx, 1 / self.sy, -self.ox / self.sx, -self.oy / self.sy)


@dataclass(frozen=True)
class Version:
    """版の鎖の1つ。geometry は親の画素 → この版の画素。親が無い・対応が分からなければ None。"""

    id: str
    width: int
    height: int
    parent_id: str | None
    geometry: Geometry | None


def relation(versions: dict[str, Version], old_id: str, new_id: str) -> Geometry | None:
    """old の画素 → new の画素の対応。共通の祖先までたどって合わせる。分からなければ None。"""

    def up(start: str) -> list[tuple[str, Geometry | None]]:
        # (版, その版の画素 → start の画素)。対応が切れたらそこで止める
        chain, acc, cur, seen = [(start, Geometry.identity())], Geometry.identity(), versions[start], {start}
        while cur.parent_id is not None and cur.parent_id in versions and cur.parent_id not in seen:
            if cur.geometry is None:
                break
            acc = cur.geometry.then(acc)
            cur = versions[cur.parent_id]
            seen.add(cur.id)
            chain.append((cur.id, acc))
        return chain

    old_chain = dict(up(old_id))
    for vid, to_new in up(new_id):
        if vid in old_chain:
            # old → 共通の祖先 → new
            return old_chain[vid].inverse().then(to_new)
    return None


def geometry_to_parent(details: dict[str, Any] | None, size: tuple[int, int], parent_size: tuple[int, int] | None):
    """版の details から、親の画素 → この版の画素の対応を決める（上の決まり）。"""
    g = (details or {}).get("geometry")
    if g:
        return Geometry.from_details(g)
    if parent_size is not None and parent_size == size:
        return Geometry.identity()
    return None


def cover(width: int, height: int, box_mm: tuple[float, float, float, float],
          base: dict[str, Any] | None = None) -> dict[str, Any]:
    a, b, c, d = box_mm
    k = max((c - a) / width, (d - b) / height)
    cx, cy = (a + c) / 2, (b + d) / 2
    w, h = width * k, height * k
    out = {**(base or {}), "crop_px": [0, 0, width, height], "dest_box_mm": [cx - w / 2, cy - h / 2, cx + w / 2,
                                                                             cy + h / 2]}
    return ImagePlacement.model_validate(out).model_dump(mode="json")


def carry(placement: dict[str, Any], old_size: tuple[int, int], new_size: tuple[int, int],
          g: Geometry) -> dict[str, Any]:
    pl = ImagePlacement.model_validate(placement)
    W, H = new_size
    ow, oh = old_size
    x0, y0, x1, y1 = pl.crop_px
    a, b, c, d = pl.dest_box_mm
    # 移した切り抜き（新しい版の画素。実数）
    mx0, my0 = x0 * g.sx + g.ox, y0 * g.sy + g.oy
    mx1, my1 = x1 * g.sx + g.ox, y1 * g.sy + g.oy
    kx, ky = (c - a) / (mx1 - mx0), (d - b) / (my1 - my0)  # mm / 新しい画素
    t = [mx0, my0, mx1, my1]
    if pl.is_identity():
        if x0 <= EDGE_TOLERANCE_PX:
            t[0] = 0
        if y0 <= EDGE_TOLERANCE_PX:
            t[1] = 0
        if x1 >= ow - EDGE_TOLERANCE_PX:
            t[2] = W
        if y1 >= oh - EDGE_TOLERANCE_PX:
            t[3] = H
    t = [min(max(t[0], 0), W), min(max(t[1], 0), H), min(max(t[2], 0), W), min(max(t[3], 0), H)]
    crop = [int(round(v)) for v in t]
    if crop[2] <= crop[0] or crop[3] <= crop[1]:
        raise Invalid("今の切り抜きが新しい版の外にある。置き場を引き継げない")
    box = [a + (crop[0] - mx0) * kx, b + (crop[1] - my0) * ky, c + (crop[2] - mx1) * kx, d + (crop[3] - my1) * ky]
    out = {**pl.model_dump(mode="json"), "crop_px": crop, "dest_box_mm": box}
    return ImagePlacement.model_validate(out).model_dump(mode="json")


def frame_bbox(frame: dict[str, Any] | None) -> tuple[float, float, float, float] | None:
    poly = (frame or {}).get("polygon_mm")
    if not poly:
        return None
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def placement_for(current_placement: dict[str, Any] | None, old: Version | None, new: Version,
                  versions: dict[str, Version], frame_box: tuple | None) -> tuple[dict[str, Any], Literal["aligned", "cover"]]:
    """新しい版の置き場と、引き継ぎ方。"""
    if current_placement is not None and old is not None:
        g = relation(versions, old.id, new.id)
        if g is not None:
            return carry(current_placement, (old.width, old.height), (new.width, new.height), g), "aligned"
    box = frame_box or (tuple(current_placement["dest_box_mm"]) if current_placement else None)
    if box is None:
        raise Invalid("コマに枠も置き場も無いので、絵をどこに置くか決められない")
    keep = {k: v for k, v in (current_placement or {}).items() if k not in ("crop_px", "dest_box_mm")}
    return cover(new.width, new.height, box, keep), "cover"
