"""ネームの案を出す・採用する・使わない操作。

案の作り手は3つ：AIが作った（ai）・人が別に作った（human）・外のネームを取り込んだ（imported）。
どの案も同じ形（name_structure の NamePage）で、採用すると同じページ・コマ・文字の行に入る。
案には作業（task）がある：name（ネーム全体）・panel_layout（コマ割りの計算の結果）。AIが案を出せるかは作業のAIの関与で決まる。

採用したときの人の手の印（V3細部の決めごと 10.2）
- 今と同じ値の項目は書かない（触ったことにしない）
- 人の案・取り込んだ案を人が採用する：人の判断なので上書きし、書いた項目に人の手の印を付ける
- AIの案（採用したのが人でもAIでも）と、AIが採用するとき：人の手の印の付いた項目と確定印のコマは書かず、
  変えようとした値を判断待ち（HeldAiChange）に置く。黙って捨てない
- 取り消すと、採用する前のページ・コマ・文字に戻す（作った行は抜く。判断待ちは withdrawn にする）
"""

from typing import Any, Literal

from pydantic import Field
from sqlalchemy import select, update

from v3server.canonical_tables.name_proposal_tables import NameProposal
from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.text_and_layer_tables import HeldAiChange, TextItem
from v3server.canonical_tables.work_tree_tables import Episode, Page, Panel
from v3server.name_structure.name_draft_schema import NamePage
from v3server.operations.ai_involvement import (
    HUMAN_EDITABLE_FIELDS,
    ROW_TASK,
    require_actor_may,
)
from v3server.operations.human_hand_guard import (
    change_with_human_hand,
    drop_unchanged,
    hold_ai_changes,
    is_human_held,
    split_ai_proposal_changes,
)
from v3server.operations.name_draft_conversion import (
    BALLOON_ITEM_KINDS,
    episode_rows,
    page_layout_from_name_page,
    panel_fields_from_name_panel,
    text_items_of_panels,
    text_values_from_name_panel,
)
from v3server.operations.operation_base import OpBase, Scope, get_in_work, work_obj
from v3server.v3_error_types import Invalid

# 採用する前の値を写す項目
_PAGE_SNAPSHOT = ("layout", "human_hand_fields", "removed")
_PANEL_SNAPSHOT = ("order", "frame", "content", "human_hand_fields", "removed")
_TEXT_SNAPSHOT = (*HUMAN_EDITABLE_FIELDS["text_items"], "human_hand_fields", "removed")


class SubmitNameProposal(OpBase):
    type: Literal["submit_name_proposal"] = "submit_name_proposal"
    id: str = Field(default_factory=new_id)
    episode_id: str
    made_by: Literal["ai", "human", "imported"]
    task: Literal["name", "panel_layout"] = "name"
    pages: list[NamePage] = Field(min_length=1)
    job_id: str | None = None
    note: str | None = None
    # 取り込んだ元の文書（MangaImport など）。変換で落とした物も残す
    source_document: dict[str, Any] | None = None

    ai_may_submit = True

    async def scope(self, session, work):
        await get_in_work(session, Episode, self.episode_id, work.id)
        return Scope("can_view", work_obj(work.id))

    async def apply(self, ctx):
        # AIの操作はAIの案、人の操作は人の案か取り込みの案（作り手を偽れない）
        if (ctx.actor.kind == "ai") != (self.made_by == "ai"):
            raise Invalid(f"{ctx.actor.kind} は made_by={self.made_by} の案を出せない")
        if self.source_document is not None and self.made_by != "imported":
            raise Invalid("元の文書を持てるのは取り込んだ案だけ")
        require_actor_may(ctx.actor, ctx.work, self.task, "propose")
        numbers = [p.page for p in self.pages]
        if len(set(numbers)) != len(numbers):
            raise Invalid("同じページ番号が2つある")
        ctx.session.add(NameProposal(
            id=self.id, work_id=ctx.work.id, episode_id=self.episode_id, made_by=self.made_by, task=self.task,
            submitted_by_kind=ctx.actor.kind, submitted_by_id=ctx.actor.id, job_id=self.job_id,
            pages=[p.model_dump(mode="json") for p in self.pages], note=self.note,
            source_document=self.source_document))
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


class _Applier:
    """1つの案を当てる間の状態。どの行をどう書いたかを写しに残し、人の手の所に当たった変更を判断待ちに置く。"""

    def __init__(self, ctx, prop: NameProposal):
        self.ctx = ctx
        self.prop = prop
        # AIの案か、AIが当てるときは、人の手の所を書かずに判断待ちへ
        self.hold = prop.made_by == "ai" or ctx.actor.kind == "ai"
        # 人の案・取り込んだ案を人が当てるときは、書いた項目に人の手の印を付ける
        self.mark_human = ctx.actor.kind == "human" and prop.made_by in ("human", "imported")
        self.snapshot: dict[str, Any] = {"pages": {}, "panels": {}, "text_items": {}, "created_pages": [],
                                         "created_panels": [], "created_text_items": []}
        self.held: list[str] = []

    def remember(self, kind: str, obj, fields: tuple[str, ...]) -> None:
        self.snapshot[kind].setdefault(obj.id, {k: getattr(obj, k) for k in fields})

    def write(self, obj, fields: dict[str, Any], page_id: str, new: bool = False) -> None:
        # 作ったばかりの行は全部の項目を書いたことにする（作るときに入れた値にも人の手の印を付けるため）
        # 未定（None）は選んだ値ではないので、作ったばかりの行でも書かない（印も付けない）
        fields = {k: v for k, v in fields.items() if v is not None} if new else drop_unchanged(obj, fields)
        if not fields:
            return
        if self.hold:
            fields, held = split_ai_proposal_changes(obj, fields)
            self.held += hold_ai_changes(self.ctx.session, self.ctx.work.id, obj, page_id, held, self.prop.id)
        if fields:
            change_with_human_hand(self.ctx.actor, obj, fields, mark_as_human=self.mark_human, work=self.ctx.work)

    def remove(self, obj, page_id: str) -> None:
        if self.hold and is_human_held(obj):
            self.held += hold_ai_changes(self.ctx.session, self.ctx.work.id, obj, page_id, {"removed": True},
                                         self.prop.id)
            return
        require_actor_may(self.ctx.actor, self.ctx.work, ROW_TASK[obj.__tablename__], "decide")
        obj.removed = True

    async def create(self, kind: str, obj) -> None:
        require_actor_may(self.ctx.actor, self.ctx.work, ROW_TASK[obj.__tablename__], "decide")
        self.ctx.session.add(obj)
        # 表どうしの関係を宣言していないので、子の行（文字）より先に書かせる
        await self.ctx.session.flush()
        self.snapshot[f"created_{kind}"].append(obj.id)

    async def sync_texts(self, panel: Panel, kinds: tuple[str, ...], values: list[dict[str, Any]] | None,
                   current: list[TextItem]) -> None:
        """コマの文字の行を、案の文字に合わせる（順に1つずつ対応させる）。案で未定なら触らない。"""
        if values is None:
            return
        rows = sorted((i for i in current if i.item_kind in kinds), key=lambda i: i.order)
        for i, vals in enumerate(values):
            if i < len(rows):
                self.remember("text_items", rows[i], _TEXT_SNAPSHOT)
                self.write(rows[i], vals, panel.page_id)
            else:
                item = TextItem(id=new_id(), work_id=self.ctx.work.id, page_id=panel.page_id, panel_id=panel.id,
                                human_hand_fields=[], removed=False, text=vals["text"], item_kind=vals["item_kind"],
                                order=vals["order"])
                await self.create("text_items", item)
                self.write(item, vals, panel.page_id, new=True)
        for row in rows[len(values):]:
            self.remember("text_items", row, _TEXT_SNAPSHOT)
            self.remove(row, panel.page_id)


class ApplyNameProposal(OpBase):
    type: Literal["apply_name_proposal"] = "apply_name_proposal"
    id: str

    ai_may_submit = True

    async def scope(self, session, work):
        prop = await get_in_work(session, NameProposal, self.id, work.id)
        return Scope("can_manage", work_obj(work.id), await _episode_page_tree(session, work.id, prop.episode_id))

    async def apply(self, ctx):
        prop = await ctx.session.get(NameProposal, self.id)
        if prop.status != "open":
            raise Invalid(f"案は {prop.status}。未決の案だけ採用できる")
        # AIが採用するのは、案の作業を任されているときだけ（書く項目ごとにも human_hand_guard が確かめる）
        require_actor_may(ctx.actor, ctx.work, prop.task, "decide")
        pages, panels_by_page = await episode_rows(ctx.session, prop.episode_id)
        items_by_panel = await text_items_of_panels(ctx.session, [p.id for ps in panels_by_page.values() for p in ps])
        by_number = {p.number: p for p in pages}
        a = _Applier(ctx, prop)
        for raw in prop.pages:
            np_ = NamePage.model_validate(raw)
            page = by_number.get(np_.page)
            if page is None:
                page = Page(id=new_id(), work_id=ctx.work.id, episode_id=prop.episode_id, number=np_.page,
                            layout={}, human_hand_fields=[], removed=False)
                await a.create("pages", page)
                panels_by_page[page.id] = []
            else:
                a.remember("pages", page, _PAGE_SNAPSHOT)
            a.write(page, {"layout": page_layout_from_name_page(np_)}, page.id,
                    new=page.id in a.snapshot["created_pages"])
            rows = sorted(panels_by_page[page.id], key=lambda r: r.order)
            for i, npanel in enumerate(sorted(np_.panels, key=lambda p: p.n)):
                fields = panel_fields_from_name_panel(npanel)
                if i < len(rows):
                    row = rows[i]
                    a.remember("panels", row, _PANEL_SNAPSHOT)
                else:
                    row = Panel(id=new_id(), work_id=ctx.work.id, page_id=page.id, order=fields["order"], frame={},
                                content={}, human_hand_fields=[], human_confirmed=False, removed=False)
                    await a.create("panels", row)
                a.write(row, fields, page.id, new=row.id in a.snapshot["created_panels"])
                balloons, sfx = text_values_from_name_panel(npanel)
                current = items_by_panel.get(row.id, [])
                await a.sync_texts(row, BALLOON_ITEM_KINDS, balloons, current)
                await a.sync_texts(row, ("drawn_sfx",), sfx, current)
            # 案に無い分のコマは抜く（人の手の所はAIの案なら判断待ちへ）
            for row in rows[len(np_.panels):]:
                a.remember("panels", row, _PANEL_SNAPSHOT)
                a.remove(row, page.id)
        prop.status = "applied"
        await ctx.session.flush()
        undo = {"type": "restore_name_snapshot", "proposal_id": self.id, "snapshot": a.snapshot}
        if a.held:
            # 判断待ちに置いた行（取り消しの操作と一緒に出来事へ残す）
            undo["held_change_ids"] = a.held
        return undo


class RestoreNameSnapshot(OpBase):
    """ApplyNameProposal の取り消し。採用する前の値に戻し、作った行を抜き、置いた判断待ちを withdrawn にする。"""

    type: Literal["restore_name_snapshot"] = "restore_name_snapshot"
    proposal_id: str
    snapshot: dict[str, Any]
    held_change_ids: list[str] | None = None

    async def scope(self, session, work):
        prop = await get_in_work(session, NameProposal, self.proposal_id, work.id)
        return Scope("can_manage", work_obj(work.id), await _episode_page_tree(session, work.id, prop.episode_id))

    async def apply(self, ctx):
        prop = await ctx.session.get(NameProposal, self.proposal_id)
        if prop.status != "applied":
            raise Invalid("採用していない案は戻せない")
        for kind, model in (("pages", Page), ("panels", Panel), ("text_items", TextItem)):
            for rid, values in self.snapshot.get(kind, {}).items():
                obj = await ctx.session.get(model, rid)
                for k, v in values.items():
                    setattr(obj, k, v)
            for rid in self.snapshot.get(f"created_{kind}", []):
                (await ctx.session.get(model, rid)).removed = True
        if self.held_change_ids:
            await ctx.session.execute(update(HeldAiChange).where(
                HeldAiChange.id.in_(self.held_change_ids), HeldAiChange.status == "open").values(status="withdrawn"))
        prop.status = "open"
        # 戻したものをもう一度採用するときは、同じ案を ApplyNameProposal で流す
        return {"type": "apply_name_proposal", "id": self.proposal_id}
