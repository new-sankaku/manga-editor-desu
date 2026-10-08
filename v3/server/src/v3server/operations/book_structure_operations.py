"""本の構成の操作：ページの並べ替えと見開き（V3細部の決めごと 1.3・15章）。

- ReorderPages：話のページの順を並べ替える（抜いていないページを全部、新しい順で渡す）。番号を 1 から振り直す。
  見開きの組が崩れる並べ替えは止める（先に見開きを解く）。取り消すと前の番号に戻る
- AddSpread：隣り合う2ページを見開きにする。組の決まりは print_export/book_layout.py
- UpdateSpread：見開きにまたがる1枚の絵と、その切り抜きと置き場（見開きの座標）・仕上げ
- 見開きを解く・戻すのは SetRemoved(target_kind="spread")

どれも人だけが出せる（本の構成と入稿の形は人が決める）。ページを足す・抜くで組が崩れたときは、
入稿前の確かめ（preflight_checks.py）と書き出しが理由を出して止める。
"""

from typing import Any, Literal

from pydantic import Field

from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.work_tree_tables import Episode, Page, Spread
from v3server.name_structure.item_styles import checked_adjustments
from v3server.operations.operation_base import OpBase, Scope, _changed, get_in_work, page_obj, work_obj
from v3server.operations.work_tree_operations import validated_placement
from v3server.print_export.book_layout import check_spreads, episode_pages, episode_spreads
from v3server.v3_error_types import Invalid


class ReorderPages(OpBase):
    type: Literal["reorder_pages"] = "reorder_pages"
    episode_id: str
    # 話の抜いていないページの全部を、新しい順で
    page_ids: list[str] = Field(min_length=1)
    # 番号をそのまま戻すとき（取り消し）だけ渡す。無ければ 1 から振る
    numbers: list[int] | None = None

    async def scope(self, session, work):
        await get_in_work(session, Episode, self.episode_id, work.id)
        pages = await episode_pages(session, self.episode_id)
        return Scope("can_manage", work_obj(work.id), [("page", p.id) for p in pages])

    async def apply(self, ctx):
        pages = await episode_pages(ctx.session, self.episode_id)
        if len(set(self.page_ids)) != len(self.page_ids):
            raise Invalid("同じページが2回ある")
        if set(self.page_ids) != {p.id for p in pages}:
            raise Invalid("話の抜いていないページを全部、1回ずつ渡す")
        if self.numbers is not None and len(self.numbers) != len(self.page_ids):
            raise Invalid("番号の数がページの数と違う")
        before_ids = [p.id for p in pages]
        before_numbers = [p.number for p in pages]
        by_id = {p.id: p for p in pages}
        for i, pid in enumerate(self.page_ids):
            by_id[pid].number = self.numbers[i] if self.numbers is not None else i + 1
        reordered = sorted(pages, key=lambda p: (p.number, self.page_ids.index(p.id)))
        if [p.id for p in reordered] != self.page_ids:
            raise Invalid("番号の順が、渡したページの順と合わない")
        broken = check_spreads(reordered, await episode_spreads(ctx.session, self.episode_id), ctx.work)
        if broken:
            raise Invalid("見開きの組が崩れる。先に見開きを解く: " + "; ".join(m for _, m in broken))
        return {"type": self.type, "episode_id": self.episode_id, "page_ids": before_ids, "numbers": before_numbers}


class AddSpread(OpBase):
    type: Literal["add_spread"] = "add_spread"
    id: str = Field(default_factory=new_id)
    first_page_id: str
    second_page_id: str

    async def scope(self, session, work):
        await get_in_work(session, Page, self.first_page_id, work.id)
        await get_in_work(session, Page, self.second_page_id, work.id)
        return Scope("can_manage", work_obj(work.id), [("page", self.first_page_id), ("page", self.second_page_id)])

    async def apply(self, ctx):
        first = await ctx.session.get(Page, self.first_page_id)
        second = await ctx.session.get(Page, self.second_page_id)
        if first.episode_id != second.episode_id:
            raise Invalid("見開きの2ページは同じ話にある")
        spread = Spread(id=self.id, work_id=ctx.work.id, episode_id=first.episode_id, first_page_id=first.id,
                        second_page_id=second.id, adjustments=[], human_hand_fields=[], removed=False)
        spreads = await episode_spreads(ctx.session, first.episode_id)
        broken = check_spreads(await episode_pages(ctx.session, first.episode_id), spreads + [spread], ctx.work)
        if broken:
            raise Invalid("見開きにできない: " + "; ".join(m for _, m in broken))
        ctx.session.add(spread)
        return {"type": "set_removed", "target_kind": "spread", "id": self.id, "removed": True}


class UpdateSpread(OpBase):
    """見開きにまたがる絵を置く・替える・外す。絵の座標は見開きの基本枠の座標（canonical_tables の Spread）。"""

    type: Literal["update_spread"] = "update_spread"
    id: str
    image_id: str | None = None
    image_placement: dict[str, Any] | None = None
    adjustments: list[dict[str, Any]] | None = None

    async def scope(self, session, work):
        s = await get_in_work(session, Spread, self.id, work.id)
        return Scope("can_draw", page_obj(s.first_page_id), [("page", s.first_page_id), ("page", s.second_page_id)])

    async def apply(self, ctx):
        spread = await ctx.session.get(Spread, self.id)
        if spread.removed:
            raise Invalid("解いた見開きは変えられない")
        changes = self.model_dump(exclude={"type", "id"}, exclude_unset=True, mode="json")
        if not changes:
            raise Invalid("変える項目がない")
        if changes.get("adjustments", []) is None:
            raise Invalid("adjustments は空にできない（外すときは []）")
        if "adjustments" in changes:
            changes["adjustments"] = checked_adjustments(changes["adjustments"])
        image_id = changes.get("image_id", spread.image_id)
        placement = changes.get("image_placement", spread.image_placement if "image_id" not in changes else None)
        changes["image_placement"] = await validated_placement(ctx.session, ctx.work.id, placement, image_id)
        before = _changed(spread, changes)
        return {"type": self.type, "id": self.id, **before}
