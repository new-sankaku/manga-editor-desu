"""ネームの案を出す・採用する・使わない操作。

案の作り手は3つ：AIが作った（ai）・人が別に作った（human）・外のネームを取り込んだ（imported）。
どの案も同じ形（name_structure の NamePage）で、採用すると同じページとコマの行に入る。

採用したときの人の手の印（V3細部の決めごと 10.2）
- 人が採用する：人の判断なので上書きする。人が作った案・取り込んだ案なら書いた項目に人の手の印を付け、AIの案なら外す
- AIが採用する（AIの関与を上げた作品）：人の手の所と確定印のコマは書かず、残した所を出来事に残す
- 取り消すと、採用する前のページとコマに戻す（作ったページとコマは抜く）
"""

from typing import Any, Literal

from pydantic import Field
from sqlalchemy import select

from v3server.canonical_tables.name_proposal_tables import NameProposal
from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.work_tree_tables import Episode, Page, Panel
from v3server.name_structure.name_draft_schema import NamePage
from v3server.operations.human_hand_guard import (
    change_with_human_hand,
    split_by_human_hand,
)
from v3server.operations.name_draft_conversion import (
    episode_rows,
    page_layout_from_name_page,
    panel_fields_from_name_panel,
)
from v3server.operations.operation_base import OpBase, Scope, get_in_work, work_obj
from v3server.v3_error_types import Invalid

# 採用する前の値を写す項目
_PAGE_SNAPSHOT = ("layout", "human_hand_fields", "removed")
_PANEL_SNAPSHOT = ("order", "frame", "content", "human_hand_fields", "removed")


class SubmitNameProposal(OpBase):
    type: Literal["submit_name_proposal"] = "submit_name_proposal"
    id: str = Field(default_factory=new_id)
    episode_id: str
    made_by: Literal["ai", "human", "imported"]
    pages: list[NamePage] = Field(min_length=1)
    job_id: str | None = None
    note: str | None = None

    async def scope(self, session, work):
        await get_in_work(session, Episode, self.episode_id, work.id)
        return Scope("can_view", work_obj(work.id))

    async def apply(self, ctx):
        # AIの操作はAIの案、人の操作は人の案か取り込みの案（作り手を偽れない）
        if (ctx.actor.kind == "ai") != (self.made_by == "ai"):
            raise Invalid(f"{ctx.actor.kind} は made_by={self.made_by} の案を出せない")
        numbers = [p.page for p in self.pages]
        if len(set(numbers)) != len(numbers):
            raise Invalid("同じページ番号が2つある")
        ctx.session.add(NameProposal(
            id=self.id, work_id=ctx.work.id, episode_id=self.episode_id, made_by=self.made_by,
            submitted_by_kind=ctx.actor.kind, submitted_by_id=ctx.actor.id, job_id=self.job_id,
            pages=[p.model_dump() for p in self.pages], note=self.note))
        return {"type": "set_name_proposal_status", "id": self.id, "status": "discarded"}


class SetNameProposalStatus(OpBase):
    """案を使わないことにする・未決に戻す。採用は ApplyNameProposal で行う。"""

    type: Literal["set_name_proposal_status"] = "set_name_proposal_status"
    id: str
    status: Literal["open", "discarded"]

    async def scope(self, session, work):
        await get_in_work(session, NameProposal, self.id, work.id)
        return Scope("can_view", work_obj(work.id))

    async def apply(self, ctx):
        prop = await ctx.session.get(NameProposal, self.id)
        if prop.status == "applied":
            raise Invalid("採用した案は、採用を取り消してから変える")
        if prop.status == self.status:
            raise Invalid("すでにその状態")
        before = prop.status
        prop.status = self.status
        return {"type": self.type, "id": self.id, "status": before}


async def _episode_page_tree(session, work_id: str, episode_id: str) -> list[tuple[str, str]]:
    pages = (await session.execute(select(Page.id).where(Page.work_id == work_id, Page.episode_id == episode_id))).scalars()
    return [("page", pid) for pid in pages]


class ApplyNameProposal(OpBase):
    type: Literal["apply_name_proposal"] = "apply_name_proposal"
    id: str

    async def scope(self, session, work):
        prop = await get_in_work(session, NameProposal, self.id, work.id)
        return Scope("can_manage", work_obj(work.id), await _episode_page_tree(session, work.id, prop.episode_id))

    async def apply(self, ctx):
        prop = await ctx.session.get(NameProposal, self.id)
        if prop.status != "open":
            raise Invalid(f"案は {prop.status}。未決の案だけ採用できる")
        pages, panels_by_page = await episode_rows(ctx.session, prop.episode_id)
        by_number = {p.number: p for p in pages}
        human_made = ctx.actor.kind == "human" and prop.made_by in ("human", "imported")
        snapshot: dict[str, Any] = {"pages": {}, "panels": {}, "created_pages": [], "created_panels": []}
        kept: list[dict[str, Any]] = []
        proposal_numbers = set()
        for raw in prop.pages:
            np_ = NamePage.model_validate(raw)
            proposal_numbers.add(np_.page)
            page = by_number.get(np_.page)
            if page is None:
                page = Page(id=new_id(), work_id=ctx.work.id, episode_id=prop.episode_id, number=np_.page,
                            layout={}, human_hand_fields=[], removed=False)
                ctx.session.add(page)
                snapshot["created_pages"].append(page.id)
                panels_by_page[page.id] = []
            else:
                snapshot["pages"][page.id] = {k: getattr(page, k) for k in _PAGE_SNAPSHOT}
            self._write(ctx, page, {"layout": page_layout_from_name_page(np_)}, human_made, kept)
            rows = sorted(panels_by_page[page.id], key=lambda r: r.order)
            for i, npanel in enumerate(sorted(np_.panels, key=lambda p: p.n)):
                fields = panel_fields_from_name_panel(npanel)
                if i < len(rows):
                    row = rows[i]
                    snapshot["panels"][row.id] = {k: getattr(row, k) for k in _PANEL_SNAPSHOT}
                    self._write(ctx, row, fields, human_made, kept)
                else:
                    row = Panel(id=new_id(), work_id=ctx.work.id, page_id=page.id, order=fields["order"], frame={},
                                content={}, human_hand_fields=[], human_confirmed=False, removed=False)
                    ctx.session.add(row)
                    snapshot["created_panels"].append(row.id)
                    self._write(ctx, row, fields, human_made, kept)
            # 案に無い分のコマは抜く（人の手の所はAIなら残す）
            for row in rows[len(np_.panels):]:
                snapshot["panels"][row.id] = {k: getattr(row, k) for k in _PANEL_SNAPSHOT}
                self._remove(ctx, row, kept)
        prop.status = "applied"
        await ctx.session.flush()
        undo = {"type": "restore_name_snapshot", "proposal_id": self.id, "snapshot": snapshot}
        if kept:
            # 残した所は取り消しの操作と一緒に出来事へ残す（payload は窓口が記録する）
            undo["kept_human_hand"] = kept
        return undo

    @staticmethod
    def _write(ctx, obj, fields: dict[str, Any], human_made: bool, kept: list) -> None:
        allowed, held = split_by_human_hand(ctx.actor, obj, fields)
        if held:
            kept.append({"target": f"{obj.__tablename__}:{obj.id}", "fields": held})
        if allowed:
            change_with_human_hand(ctx.actor, obj, allowed, mark_as_human=human_made)

    @staticmethod
    def _remove(ctx, row: Panel, kept: list) -> None:
        if ctx.actor.kind == "ai" and (row.human_hand_fields or row.human_confirmed):
            kept.append({"target": f"panels:{row.id}", "fields": ["removed"]})
            return
        row.removed = True


class RestoreNameSnapshot(OpBase):
    """ApplyNameProposal の取り消し。採用する前の値に戻し、作ったページとコマを抜く。"""

    type: Literal["restore_name_snapshot"] = "restore_name_snapshot"
    proposal_id: str
    snapshot: dict[str, Any]
    kept_human_hand: list[dict[str, Any]] | None = None

    async def scope(self, session, work):
        prop = await get_in_work(session, NameProposal, self.proposal_id, work.id)
        return Scope("can_manage", work_obj(work.id), await _episode_page_tree(session, work.id, prop.episode_id))

    async def apply(self, ctx):
        prop = await ctx.session.get(NameProposal, self.proposal_id)
        if prop.status != "applied":
            raise Invalid("採用していない案は戻せない")
        for pid, values in self.snapshot["pages"].items():
            page = await ctx.session.get(Page, pid)
            for k, v in values.items():
                setattr(page, k, v)
        for rid, values in self.snapshot["panels"].items():
            row = await ctx.session.get(Panel, rid)
            for k, v in values.items():
                setattr(row, k, v)
        for pid in self.snapshot["created_pages"]:
            (await ctx.session.get(Page, pid)).removed = True
        for rid in self.snapshot["created_panels"]:
            (await ctx.session.get(Panel, rid)).removed = True
        prop.status = "open"
        # 戻したものをもう一度採用するときは、同じ案を ApplyNameProposal で流す
        return {"type": "apply_name_proposal", "id": self.proposal_id}
