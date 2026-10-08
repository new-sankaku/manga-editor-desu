"""コマ枠の道具とナイフ（V3細部の決めごと 10.1・10.4）。どれも1回の操作で、1回で取り消せる（取り消しは RestoreRows）。

- split_panel（ナイフ・コマ枠の「分ける」）：押した点を通る横・縦・斜めの線で分ける。間の幅は「コマの間」
  （page_spec の gutter。横の線は gutter_y、縦の線は gutter_x、斜めは近い方）か、gap_mm で渡す。
  絵（コマの絵・層・トーン）は大きい側に残る。小さい側が新しいコマになり、そこに入る文字・トーン・図形は新しいコマへ移す
- merge_panels（コマ枠の「合わせる」）：隣り合う2つを、両方を包む1つの形にする。中身は大きい側のものが残る。
  隣り合っていない（間がコマの間より広い）2つと、包んだ形がほかのコマに重なる2つは受け付けない
- random_split_panel（ばらばらに割る）：横と縦の切る数と種で、ランダムに割る
- add_shape_panel（図形のコマ）：形の名前と箱から多角形の枠を作る
- save_panel_template・apply_panel_template（コマの型）

細すぎる分け方は、閾値 panel_short_side_min_mm（コマの最小の大きさ）より狭い形ができるときに断る。閾値が無ければ分けない。
コマの番号（order）は作品の通し番号なので、分ける・合わせると後ろのコマの番号がずれる。ずれるコマのページもロックを確かめる。
AIがこの操作を出し、当たる行に人の手の印があれば、操作ごと判断待ちに置く（human_hand_guard.hold_ai_operation）。
"""

from typing import Any, Literal

from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.page_item_tables import PageItem, PanelTemplate
from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.text_and_layer_tables import PanelLayer, TextItem
from v3server.canonical_tables.threshold_and_finding_tables import Threshold
from v3server.canonical_tables.work_tree_tables import Page, Panel
from v3server.name_structure.item_styles import FrameStyle
from v3server.name_structure.name_draft_schema import PanelFrame
from v3server.name_structure.reading_direction import PageSpec
from v3server.operations.ai_involvement import require_actor_may
from v3server.operations.human_hand_guard import (
    hold_ai_operation,
    refuse_if_fixed,
    touches_human_hand,
)
from v3server.operations.operation_base import OpBase, Scope, get_in_work, page_obj
from v3server.operations.row_snapshot import RowChanges
from v3server.panel_layout.panel_frame_editing import (
    FrameEditError,
    FrameShape,
    are_adjacent,
    line_normal,
    merged_polygon,
    random_split,
    reading_first,
    shape_polygon,
    split_polygon,
)
from v3server.panel_layout.panel_geometry import (
    point_in_polygon,
    polygon_area,
    polygon_overlap_area,
)
from v3server.v3_error_types import Invalid

# 今のアプリ（js/panel/random-cut.js）と同じく、1回の切りに試す回数
RANDOM_SPLIT_ATTEMPTS_PER_CUT = 2


# コマの最小の大きさの閾値（ナイフ・ばらばらに割る・割りの案で同じ値を使う）
MIN_PANEL_KEY = "panel_short_side_min_mm"


async def min_panel_mm(session: AsyncSession, work_id: str) -> float:
    t = (await session.execute(select(Threshold).where(
        Threshold.work_id == work_id, Threshold.key == MIN_PANEL_KEY))).scalar_one_or_none()
    if t is None or t.status == "rejected":
        raise Invalid(f"閾値 {MIN_PANEL_KEY} が無い。コマの最小の大きさが決まらないので割りを計算しない")
    return float(t.value["value"])


def page_spec_of(work) -> PageSpec:
    if not work.page_spec:
        raise Invalid("作品の寸法（page_spec）が決まっていないので、コマの間が分からない")
    return PageSpec.model_validate(work.page_spec)


def _poly(panel: Panel) -> list[tuple[float, float]]:
    if not panel.frame:
        raise Invalid(f"コマ {panel.id} には枠がまだ無い")
    return [tuple(p) for p in panel.frame["polygon_mm"]]


def _frame(poly, bleeds: bool) -> dict[str, Any]:
    return PanelFrame(polygon_mm=[(float(x), float(y)) for x, y in poly], bleeds=bleeds).model_dump(mode="json")


async def _live_work_panels(session, work_id: str) -> list[Panel]:
    q = select(Panel).join(Page, Page.id == Panel.page_id).where(
        Panel.work_id == work_id, Panel.removed.is_(False), Page.removed.is_(False))
    return list((await session.execute(q)).scalars())


async def _items_in(session, panel_id: str) -> tuple[list[TextItem], list[PageItem]]:
    texts = (await session.execute(select(TextItem).where(TextItem.panel_id == panel_id,
                                                          TextItem.removed.is_(False)))).scalars().all()
    items = (await session.execute(select(PageItem).where(PageItem.panel_id == panel_id,
                                                          PageItem.removed.is_(False)))).scalars().all()
    return list(texts), list(items)


def _box_center(box) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


async def _shift_scope(session, work, page_id: str, after_order: int, extra: list[tuple[str, str]]) -> Scope:
    pages = {page_id} | {p.page_id for p in await _live_work_panels(session, work.id) if p.order > after_order}
    locks = [("page", p) for p in sorted(pages)] + extra
    return Scope("can_draw", page_obj(page_id), locks, page_tree=page_id)


class _Plan:
    """操作の中身を、当てる前に組む。AIが人の手の所に当たるかを、正本を変える前に確かめるため。"""

    def __init__(self):
        self.changes: list[tuple[Any, dict[str, Any], bool]] = []  # (行, 変える値, 人の手の印をそのまま残すか)
        self.removes: list[Any] = []
        self.creates: list[Any] = []

    def change(self, obj, values: dict[str, Any], keep_marks: bool = False) -> None:
        self.changes.append((obj, values, keep_marks))

    def touched_human_hand(self) -> bool:
        return (any(touches_human_hand(o, set(v)) for o, v, _ in self.changes)
                or any(touches_human_hand(o, {"removed"}) or bool(o.human_hand_fields) for o in self.removes))

    def apply(self, ctx, op: OpBase, page_ids: list[str], target, label: str) -> dict[str, Any]:
        for o, _, keep_marks in self.changes:
            if not keep_marks:
                refuse_if_fixed(o)
        for o in self.removes:
            refuse_if_fixed(o)
        rc = RowChanges(ctx)
        if ctx.actor.kind == "ai" and self.touched_human_hand():
            # 何も変えない。取り消すと、置いた判断待ちを下げるだけになる（窓口が包む）
            hold_ai_operation(ctx, op.model_dump(mode="json"), target, page_ids[0], "人の手の印の付いたコマ・文字に当たる")
            return rc.inverse(page_ids, label)
        for o, values, keep_marks in self.changes:
            if keep_marks:
                # 番号のずれは数え直しで、物を動かすのではない。人の手の印も「動かさない」もそのまま
                rc.renumber(o, values)
            else:
                rc.change(o, values)
        for o in self.removes:
            rc.remove(o)
        for o in self.creates:
            rc.created(o)
        return rc.inverse(page_ids, label)


def _new_panel(ctx, page_id: str, order: int, frame: dict[str, Any], frame_style, pid: str | None = None) -> Panel:
    human = ctx.actor.kind == "human"
    return Panel(id=pid or new_id(), work_id=ctx.work.id, page_id=page_id, order=order, frame=frame, role=None,
                 content={}, frame_style=frame_style, adjustments=[], fixed=False, human_confirmed=False,
                 human_hand_fields=sorted(["frame", "order"] + (["frame_style"] if frame_style else [])) if human else [],
                 removed=False)


async def _shift_orders(plan: _Plan, session, work_id: str, after_order: int, delta: int, exclude: set[str]) -> list[str]:
    pages = []
    for p in await _live_work_panels(session, work_id):
        if p.order > after_order and p.id not in exclude:
            plan.change(p, {"order": p.order + delta}, keep_marks=True)
            pages.append(p.page_id)
    return pages


class SplitPanel(OpBase):
    type: Literal["split_panel"] = "split_panel"
    panel_id: str
    # 押した点（基本枠の mm）
    through_mm: tuple[float, float]
    direction: Literal["horizontal", "vertical", "slanted"]
    # 斜めのときの線の角度（度。横から時計回り）
    angle_deg: float | None = None
    # 分けた間の幅（mm）。無ければ作品のコマの間
    gap_mm: float | None = Field(default=None, ge=0)
    new_panel_id: str = Field(default_factory=new_id)

    ai_may_submit = True

    async def scope(self, session, work):
        panel = await get_in_work(session, Panel, self.panel_id, work.id)
        return await _shift_scope(session, work, panel.page_id, panel.order, [("panel", panel.id)])

    async def apply(self, ctx):
        require_actor_may(ctx.actor, ctx.work, "panel_layout", "decide")
        panel = await ctx.session.get(Panel, self.panel_id)
        if panel.removed:
            raise Invalid("抜いたコマは分けられない")
        spec = page_spec_of(ctx.work)
        gap = self.gap_mm
        if gap is None:
            horizontal_like = self.direction == "horizontal" or (
                self.direction == "slanted" and abs(((self.angle_deg or 0) + 90) % 180 - 90) < 45)
            gap = spec.gutter_y_mm if horizontal_like else spec.gutter_x_mm
        try:
            a, b = split_polygon(_poly(panel), self.through_mm, line_normal(self.direction, self.angle_deg), gap,
                                 await min_panel_mm(ctx.session, ctx.work.id))
        except FrameEditError as e:
            raise Invalid(f"分けられない: {e}") from e
        big, small = (a, b) if polygon_area(a) >= polygon_area(b) else (b, a)
        small_first = reading_first(small, big, ctx.work.reading_direction) == 0
        plan = _Plan()
        pages = [panel.page_id] + await _shift_orders(plan, ctx.session, ctx.work.id, panel.order, 1, {panel.id})
        bleeds = panel.frame.get("bleeds", False)
        plan.change(panel, {"frame": _frame(big, bleeds)} | ({"order": panel.order + 1} if small_first else {}))
        new = _new_panel(ctx, panel.page_id, panel.order if small_first else panel.order + 1, _frame(small, bleeds),
                         panel.frame_style, self.new_panel_id)
        plan.creates.append(new)
        texts, items = await _items_in(ctx.session, panel.id)
        for t in texts:
            if t.box_mm is not None and point_in_polygon(_box_center(t.box_mm), small):
                plan.change(t, {"panel_id": new.id})
        for it in items:
            if point_in_polygon(_box_center(it.box_mm), small):
                plan.change(it, {"panel_id": new.id})
        return plan.apply(ctx, self, pages, panel, "コマを分ける")


class MergePanels(OpBase):
    type: Literal["merge_panels"] = "merge_panels"
    panel_ids: tuple[str, str]

    ai_may_submit = True

    async def scope(self, session, work):
        a = await get_in_work(session, Panel, self.panel_ids[0], work.id)
        b = await get_in_work(session, Panel, self.panel_ids[1], work.id)
        if a.page_id != b.page_id:
            raise Invalid("合わせられるのは同じページのコマだけ")
        return await _shift_scope(session, work, a.page_id, min(a.order, b.order),
                                  [("panel", a.id), ("panel", b.id)])

    async def apply(self, ctx):
        require_actor_may(ctx.actor, ctx.work, "panel_layout", "decide")
        if self.panel_ids[0] == self.panel_ids[1]:
            raise Invalid("同じコマは合わせられない")
        a, b = [await ctx.session.get(Panel, i) for i in self.panel_ids]
        if a.removed or b.removed:
            raise Invalid("抜いたコマは合わせられない")
        spec = page_spec_of(ctx.work)
        pa, pb = _poly(a), _poly(b)
        if not are_adjacent(pa, pb, max(spec.gutter_x_mm, spec.gutter_y_mm)):
            raise Invalid("隣り合っていない2つのコマは合わせられない（間がコマの間より広い）")
        hull = merged_polygon(pa, pb)
        others = [p for p in await _live_work_panels(ctx.session, ctx.work.id)
                  if p.page_id == a.page_id and p.id not in (a.id, b.id) and p.frame]
        for p in others:
            if polygon_overlap_area(hull, _poly(p)) > 1e-6:
                raise Invalid(f"合わせた形がほかのコマ（番号 {p.order}）に重なる")
        keep, gone = (a, b) if polygon_area(pa) >= polygon_area(pb) else (b, a)
        plan = _Plan()
        plan.change(keep, {"frame": _frame(hull, a.frame.get("bleeds", False) or b.frame.get("bleeds", False))}
                    | ({"order": gone.order} if gone.order < keep.order else {}))
        plan.removes.append(gone)
        texts, items = await _items_in(ctx.session, gone.id)
        for t in texts + items:
            plan.change(t, {"panel_id": keep.id})
        pages = [a.page_id] + await _shift_orders(plan, ctx.session, ctx.work.id, max(a.order, b.order), -1,
                                                  {a.id, b.id})
        return plan.apply(ctx, self, pages, keep, "コマを合わせる")


class RandomSplitPanel(OpBase):
    type: Literal["random_split_panel"] = "random_split_panel"
    panel_id: str
    horizontal_cuts: int = Field(ge=0)
    vertical_cuts: int = Field(ge=0)
    # 同じ種なら同じ割りになる（出来事に残るので、やり直しても同じ）
    seed: int
    new_panel_ids: list[str] | None = None

    ai_may_submit = True

    async def scope(self, session, work):
        panel = await get_in_work(session, Panel, self.panel_id, work.id)
        return await _shift_scope(session, work, panel.page_id, panel.order, [("panel", panel.id)])

    async def apply(self, ctx):
        require_actor_may(ctx.actor, ctx.work, "panel_layout", "decide")
        if self.horizontal_cuts + self.vertical_cuts == 0:
            raise Invalid("切る数が0")
        panel = await ctx.session.get(Panel, self.panel_id)
        spec = page_spec_of(ctx.work)
        try:
            pieces = random_split(_poly(panel), self.horizontal_cuts, self.vertical_cuts, spec.gutter_x_mm,
                                  spec.gutter_y_mm, await min_panel_mm(ctx.session, ctx.work.id), self.seed,
                                  RANDOM_SPLIT_ATTEMPTS_PER_CUT, ctx.work.reading_direction)
        except FrameEditError as e:
            raise Invalid(f"割れない: {e}") from e
        ids = self.new_panel_ids or [new_id() for _ in pieces[1:]]
        if len(ids) != len(pieces) - 1:
            raise Invalid(f"新しいコマの id は {len(pieces) - 1} 個要る")
        big = max(range(len(pieces)), key=lambda i: polygon_area(pieces[i]))
        plan = _Plan()
        pages = [panel.page_id] + await _shift_orders(plan, ctx.session, ctx.work.id, panel.order, len(pieces) - 1,
                                                      {panel.id})
        bleeds = panel.frame.get("bleeds", False)
        texts, items = await _items_in(ctx.session, panel.id)
        new_ids = iter(ids)
        for i, piece in enumerate(pieces):
            order = panel.order + i
            if i == big:
                plan.change(panel, {"frame": _frame(piece, bleeds)} | ({"order": order} if order != panel.order else {}))
                continue
            new = _new_panel(ctx, panel.page_id, order, _frame(piece, bleeds), panel.frame_style, next(new_ids))
            plan.creates.append(new)
            for t in texts:
                if t.box_mm is not None and point_in_polygon(_box_center(t.box_mm), piece):
                    plan.change(t, {"panel_id": new.id})
            for it in items:
                if point_in_polygon(_box_center(it.box_mm), piece):
                    plan.change(it, {"panel_id": new.id})
        return plan.apply(ctx, self, pages, panel, "ばらばらに割る")


class AddShapePanel(OpBase):
    """図形のコマを足す。番号は add_panel と同じく、渡した order のまま（後ろのコマはずらさない）。"""

    type: Literal["add_shape_panel"] = "add_shape_panel"
    id: str = Field(default_factory=new_id)
    page_id: str
    order: int
    shape: FrameShape
    box_mm: tuple[float, float, float, float]
    bleeds: bool = False
    frame_style: FrameStyle | None = None

    ai_may_submit = True

    async def scope(self, session, work):
        await get_in_work(session, Page, self.page_id, work.id)
        return Scope("can_draw", page_obj(self.page_id), [("page", self.page_id)])

    async def apply(self, ctx):
        require_actor_may(ctx.actor, ctx.work, "panel_layout", "decide")
        try:
            poly = shape_polygon(self.shape, self.box_mm)
        except FrameEditError as e:
            raise Invalid(str(e)) from e
        style = (self.frame_style.model_copy(update={"shape": self.shape}).model_dump(mode="json")
                 if self.frame_style else None)
        rc = RowChanges(ctx)
        rc.created(_new_panel(ctx, self.page_id, self.order, _frame(poly, self.bleeds), style, self.id))
        return rc.inverse([self.page_id], "図形のコマを足す")


class SavePanelTemplate(OpBase):
    """今のページの枠の並びを、コマの型として残す。"""

    type: Literal["save_panel_template"] = "save_panel_template"
    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1)
    page_id: str

    async def scope(self, session, work):
        await get_in_work(session, Page, self.page_id, work.id)
        return Scope("can_draw", page_obj(self.page_id))

    async def apply(self, ctx):
        spec = page_spec_of(ctx.work)
        panels = [p for p in await _live_work_panels(ctx.session, ctx.work.id) if p.page_id == self.page_id and p.frame]
        if not panels:
            raise Invalid("枠のあるコマが無い")
        frames = [{"polygon": [[x / spec.frame_width_mm, y / spec.frame_height_mm] for x, y in _poly(p)],
                   "bleeds": p.frame.get("bleeds", False), "frame_style": p.frame_style}
                  for p in sorted(panels, key=lambda p: p.order)]
        rc = RowChanges(ctx)
        rc.created(PanelTemplate(id=self.id, work_id=ctx.work.id, name=self.name, frames=frames,
                                 created_by=ctx.actor.id, human_hand_fields=["frames", "name"], removed=False))
        return rc.inverse([], "コマの型を残す")


class ApplyPanelTemplate(OpBase):
    """コマの型をページに当てる。ページの今のコマは抜く。絵・層・文字・トーン・図形の入ったコマがあれば当てない
    （中身が行き場を失うため。先に中身を動かすか、コマを抜く）。"""

    type: Literal["apply_panel_template"] = "apply_panel_template"
    page_id: str
    template_id: str
    # 1つ目のコマの番号
    first_order: int
    new_panel_ids: list[str] | None = None

    ai_may_submit = True

    async def scope(self, session, work):
        await get_in_work(session, PanelTemplate, self.template_id, work.id)
        await get_in_work(session, Page, self.page_id, work.id)
        return Scope("can_draw", page_obj(self.page_id), [("page", self.page_id)], page_tree=self.page_id)

    async def apply(self, ctx):
        require_actor_may(ctx.actor, ctx.work, "panel_layout", "decide")
        tpl = await ctx.session.get(PanelTemplate, self.template_id)
        if tpl.removed:
            raise Invalid("抜いた型は当てられない")
        spec = page_spec_of(ctx.work)
        current = [p for p in await _live_work_panels(ctx.session, ctx.work.id) if p.page_id == self.page_id]
        for p in current:
            texts, items = await _items_in(ctx.session, p.id)
            layers = (await ctx.session.execute(select(PanelLayer.id).where(
                PanelLayer.panel_id == p.id, PanelLayer.removed.is_(False)))).first()
            if p.image_id or texts or items or layers:
                raise Invalid(f"コマ（番号 {p.order}）に中身がある。先に中身を動かすか、コマを抜く")
        ids = self.new_panel_ids or [new_id() for _ in tpl.frames]
        if len(ids) != len(tpl.frames):
            raise Invalid(f"新しいコマの id は {len(tpl.frames)} 個要る")
        plan = _Plan()
        plan.removes.extend(current)
        for i, (f, pid) in enumerate(zip(tpl.frames, ids, strict=False)):
            poly = [(x * spec.frame_width_mm, y * spec.frame_height_mm) for x, y in f["polygon"]]
            plan.creates.append(_new_panel(ctx, self.page_id, self.first_order + i, _frame(poly, f["bleeds"]),
                                           f.get("frame_style"), pid))
        page = await ctx.session.get(Page, self.page_id)
        return plan.apply(ctx, self, [self.page_id], page, "コマの型を当てる")

