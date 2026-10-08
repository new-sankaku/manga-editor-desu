"""ペン・消しゴムの操作（V3細部の決めごと 10.1）。人だけが出せる（人の手の道具）。

線が正本（PenStroke）。人の手の層の絵は、線から作った控え（cache）：
- 控えは画面（ブラウザ）が描いて上げる（SetStrokeCache）。今のアプリの筆（fabric.js）を画面が持っているので、
  画面で見えている絵と控えが同じになる。サーバーは筆を描かない
- 線を足す・変える・消すたびに、層の stroke_revision が1つ進む。控えには、どの版から作ったか（image_stroke_revision）を残す。
  2つが違えば控えは古い。古い控えは、AIへ渡すマスクにも書き出しにも使わない（止める）

操作（どれも1回で取り消せ、変えた線に人の手の印が付く）：
- AddPenStrokes：線を足す
- UpdatePenStrokes：選んだ線（1本でも何本でも）を動かす・太さ・色・不透明度・筆を変える
- RemovePenStrokes：選んだ線を消す
- ErasePenStrokes：線の消しゴム（whole・to_crossings・touched。hand_tools/vector_strokes.py）
- SetStrokeCache：控えの絵を層に付ける
- ErasePixels：AIの絵の層（線を持たない絵）を画素で消す。新しい版（human_edited）と、消した所の人の手の範囲を作る
"""

from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import select

from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.page_item_tables import PenStroke
from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.text_and_layer_tables import PanelLayer, ProtectedRegion
from v3server.canonical_tables.work_tree_tables import Panel
from v3server.hand_tools.pen_stroke_raster import PixelEraserStroke
from v3server.hand_tools.vector_strokes import EraseMode, StrokeValues, erase, moved
from v3server.operations.image_file_operations import RegisterImage
from v3server.operations.operation_base import OpBase, Scope, get_in_work, page_obj
from v3server.operations.row_snapshot import RowChanges
from v3server.v3_error_types import Invalid


async def _hand_layer(session, work_id: str, layer_id: str) -> PanelLayer:
    layer = await get_in_work(session, PanelLayer, layer_id, work_id)
    if layer.role != "human_hand":
        raise Invalid("ペンの線を持てるのは人の手の層（role=human_hand）だけ")
    if layer.removed:
        raise Invalid("抜いた層には描けない")
    return layer


def _layer_scope(layer: PanelLayer) -> Scope:
    return Scope("can_draw", page_obj(layer.page_id),
                 [("page", layer.page_id), ("panel", layer.panel_id), ("item", layer.id)])


async def _strokes(session, work_id: str, ids: list[str]) -> list[PenStroke]:
    if not ids or len(set(ids)) != len(ids):
        raise Invalid("線の id が空か、重なっている")
    out = []
    for i in ids:
        s = await get_in_work(session, PenStroke, i, work_id)
        if s.removed:
            raise Invalid(f"線 {i} はもう消してある")
        out.append(s)
    if len({s.layer_id for s in out}) != 1:
        raise Invalid("一度に扱えるのは1つの層の線だけ")
    return out


async def live_strokes(session, layer_id: str) -> list[PenStroke]:
    q = select(PenStroke).where(PenStroke.layer_id == layer_id, PenStroke.removed.is_(False))
    return list((await session.execute(q.order_by(PenStroke.stack_order))).scalars())


def _stroke_row(ctx, layer: PanelLayer, values: dict[str, Any], order: int) -> PenStroke:
    return PenStroke(id=new_id(), work_id=ctx.work.id, page_id=layer.page_id, panel_id=layer.panel_id,
                     layer_id=layer.id, stack_order=order, created_by=ctx.actor.id, fixed=False, removed=False,
                     human_hand_fields=sorted(values), **values)


def _values(v: StrokeValues) -> dict[str, Any]:
    d = v.model_dump(mode="json")
    d["points"] = [list(p) for p in d["points"]]
    return d


class AddPenStrokes(OpBase):
    type: Literal["add_pen_strokes"] = "add_pen_strokes"
    layer_id: str
    strokes: list[StrokeValues] = Field(min_length=1)

    async def scope(self, session, work):
        return _layer_scope(await _hand_layer(session, work.id, self.layer_id))

    async def apply(self, ctx):
        layer = await _hand_layer(ctx.session, ctx.work.id, self.layer_id)
        live = await live_strokes(ctx.session, layer.id)
        top = max((s.stack_order for s in live), default=-1)
        rc = RowChanges(ctx)
        for i, v in enumerate(self.strokes):
            rc.created(_stroke_row(ctx, layer, _values(v), top + 1 + i))
        rc.bump_strokes(layer)
        return rc.inverse([layer.page_id], "ペンの線を足した取り消し")


class UpdatePenStrokes(OpBase):
    """選んだ線をまとめて変える。move_mm は全部の点を動かす量。"""

    type: Literal["update_pen_strokes"] = "update_pen_strokes"
    ids: list[str]
    move_mm: tuple[float, float] | None = None
    brush: str | None = None
    width_mm: float | None = Field(default=None, gt=0)
    color: str | None = None
    opacity: float | None = Field(default=None, gt=0, le=1)
    seed: int | None = None
    brush_options: dict[str, Any] | None = None

    async def scope(self, session, work):
        strokes = await _strokes(session, work.id, self.ids)
        return _layer_scope(await _hand_layer(session, work.id, strokes[0].layer_id))

    async def apply(self, ctx):
        strokes = await _strokes(ctx.session, ctx.work.id, self.ids)
        layer = await _hand_layer(ctx.session, ctx.work.id, strokes[0].layer_id)
        changes = self.model_dump(exclude={"type", "ids", "move_mm"}, exclude_unset=True, mode="json")
        if not changes and self.move_mm is None:
            raise Invalid("変える項目がない")
        rc = RowChanges(ctx)
        for s in strokes:
            one = dict(changes)
            if self.move_mm is not None:
                one["points"] = moved(s.points, *self.move_mm)
            current = {k: getattr(s, k) for k in StrokeValues.model_fields}
            try:
                checked = _values(StrokeValues.model_validate(current | one))
            except ValueError as e:
                raise Invalid(f"線 {s.id} をその値にできない: {e}") from e
            rc.change(s, {k: checked[k] for k in one})
        rc.bump_strokes(layer)
        return rc.inverse([layer.page_id], "ペンの線を変えた取り消し")


class RemovePenStrokes(OpBase):
    type: Literal["remove_pen_strokes"] = "remove_pen_strokes"
    ids: list[str]

    async def scope(self, session, work):
        strokes = await _strokes(session, work.id, self.ids)
        return _layer_scope(await _hand_layer(session, work.id, strokes[0].layer_id))

    async def apply(self, ctx):
        strokes = await _strokes(ctx.session, ctx.work.id, self.ids)
        layer = await _hand_layer(ctx.session, ctx.work.id, strokes[0].layer_id)
        rc = RowChanges(ctx)
        for s in strokes:
            rc.remove(s)
        rc.bump_strokes(layer)
        return rc.inverse([layer.page_id], "ペンの線を消した取り消し")


class ErasePenStrokes(OpBase):
    """線の消しゴム。消しゴムの通り道（基本枠の mm）と幅で、層の線を消す・分ける。"""

    type: Literal["erase_pen_strokes"] = "erase_pen_strokes"
    layer_id: str
    mode: EraseMode
    path_mm: list[tuple[float, float]] = Field(min_length=1)
    width_mm: float = Field(gt=0)

    async def scope(self, session, work):
        return _layer_scope(await _hand_layer(session, work.id, self.layer_id))

    async def apply(self, ctx):
        layer = await _hand_layer(ctx.session, ctx.work.id, self.layer_id)
        live = await live_strokes(ctx.session, layer.id)
        rc = RowChanges(ctx)
        top = max((s.stack_order for s in live), default=-1)
        touched = 0
        for s in live:
            others = [o.points for o in live if o.id != s.id and o.brush not in ("eraser", "mosaic")]
            pieces = erase([tuple(p) for p in s.points], s.width_mm, self.path_mm, self.width_mm, self.mode, others)
            if pieces is None:
                continue
            touched += 1
            if not pieces:
                rc.remove(s)
                continue
            # 1つ目の切れ端は元の線のまま（id を変えない）。残りは新しい線にする
            rc.change(s, {"points": [list(p) for p in pieces[0]]})
            base = {k: getattr(s, k) for k in ("brush", "width_mm", "color", "opacity", "seed", "brush_options")}
            for piece in pieces[1:]:
                top += 1
                rc.created(_stroke_row(ctx, layer, base | {"points": [list(p) for p in piece]}, top))
        if not touched:
            raise Invalid("消しゴムがどの線にも触れていない")
        rc.bump_strokes(layer)
        return rc.inverse([layer.page_id], "線の消しゴムの取り消し")


class StoredResult(BaseModel):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class SetStrokeCache(OpBase):
    """画面が線から描いた控えの絵を登録し（human_drawn・human_hand・details.made_by=pen_strokes）、層に付ける。
    描いた元の線の版（stroke_revision）が今の版と違えば受けない。絵は http_routes/pen_stroke_routes.py が入口を通して置く。"""

    type: Literal["set_stroke_cache"] = "set_stroke_cache"
    layer_id: str
    stroke_revision: int
    result: StoredResult
    # 控えの絵の置き場（ImagePlacement。控えの画素 → 基本枠の mm）
    placement: dict[str, Any]
    image_id: str = Field(default_factory=new_id)

    async def scope(self, session, work):
        return _layer_scope(await _hand_layer(session, work.id, self.layer_id))

    async def apply(self, ctx):
        from v3server.operations.work_tree_operations import validated_placement

        layer = await _hand_layer(ctx.session, ctx.work.id, self.layer_id)
        if self.stroke_revision != layer.stroke_revision:
            raise Invalid(f"控えは線の版 {self.stroke_revision} から作ったが、今の版は {layer.stroke_revision}。描き直して上げる")
        await RegisterImage(id=self.image_id, role="human_hand", origin="human_drawn", page_id=layer.page_id,
                            panel_id=layer.panel_id, sha256=self.result.sha256, media_type=self.result.media_type,
                            width=self.result.width, height=self.result.height,
                            details={"made_by": "pen_strokes", "layer_id": layer.id,
                                     "stroke_revision": self.stroke_revision}).apply(ctx)
        await ctx.session.flush()
        placement = await validated_placement(ctx.session, ctx.work.id, self.placement, self.image_id)
        rc = RowChanges(ctx)
        rc.change(layer, {"image_id": self.image_id, "placement": placement})
        rc.set_plain(layer, {"image_stroke_revision": self.stroke_revision})
        return rc.inverse([layer.page_id], "線の控えを付けた取り消し")


class ErasePixels(OpBase):
    """線を持たない絵（AIの絵の層・コマの1枚の絵・持ち込んだ絵）を画素で消す。
    消した後の絵は http_routes/pen_stroke_routes.py が描いて入口を通して置き、この操作で版として登録する。"""

    type: Literal["erase_pixels"] = "erase_pixels"
    panel_id: str
    # 消す層。無ければコマの1枚の絵（Panel.image_id）
    layer_id: str | None = None
    base_image_id: str
    strokes: list[PixelEraserStroke] = Field(min_length=1)
    result: StoredResult
    erase_mask_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_image_id: str = Field(default_factory=new_id)

    async def scope(self, session, work):
        panel = await get_in_work(session, Panel, self.panel_id, work.id)
        locks = [("page", panel.page_id), ("panel", panel.id)]
        if self.layer_id is not None:
            locks.append(("item", self.layer_id))
        return Scope("can_draw", page_obj(panel.page_id), locks)

    async def apply(self, ctx):
        panel = await ctx.session.get(Panel, self.panel_id)
        if self.layer_id is not None:
            target = await get_in_work(ctx.session, PanelLayer, self.layer_id, ctx.work.id)
            if target.panel_id != panel.id:
                raise Invalid("層がそのコマの物ではない")
            if target.role == "human_hand" and await live_strokes(ctx.session, target.id):
                raise Invalid("ペンの線を持つ層は、線の消しゴム（erase_pen_strokes）で消す")
            role = target.role
        else:
            target, role = panel, "panel_art"
        if target.image_id != self.base_image_id:
            raise Invalid("消している間に絵が替わった。今の絵で消し直す")
        base = await ctx.session.get(ImageFile, self.base_image_id)
        if (base.width, base.height) != (self.result.width, self.result.height):
            raise Invalid("消した後の絵の大きさが元の絵と違う")
        await RegisterImage(id=self.result_image_id, role=role, origin="human_edited", page_id=panel.page_id,
                            panel_id=panel.id, based_on_image_id=self.base_image_id, sha256=self.result.sha256,
                            media_type=self.result.media_type, width=self.result.width, height=self.result.height,
                            details={"made_by": "erase_pixels",
                                     "strokes": [s.model_dump(mode="json") for s in self.strokes]}).apply(ctx)
        rc = RowChanges(ctx)
        rc.change(target, {"image_id": self.result_image_id})
        rc.created(ProtectedRegion(id=new_id(), work_id=ctx.work.id, image_id=self.result_image_id,
                                   page_id=panel.page_id, polygon_px=None, mask_sha256=self.erase_mask_sha256,
                                   note="消しゴムで消した所", created_by=ctx.actor.id, removed=False))
        return rc.inverse([panel.page_id], "画素の消しゴムの取り消し")
