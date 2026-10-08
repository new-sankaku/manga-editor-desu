"""ページと作品の確認の状態（下書き・確認待ち・承認・直しが要る）を変える操作（V3点検の結果 5章の6）。

状態の行（review_states）が無いものは下書き。変えるたびに記録（review_records）を1行足し、コメントも残す。

移り方と、それを出せる人（openfga/model.fga の関係）
- 出す：下書き → 確認待ち、直しが要る → 確認待ち、確認待ち → 下書き（出したのを引っ込める）
  ページは描ける人（ページの can_draw）、作品は作者（can_manage）
- 決める：確認待ち → 承認、確認待ち → 直しが要る、承認 → 下書き（承認を開け直す）
  作品の can_approve（作者・編集）。直しが要るにはコメントが要る
上のどれでもない移り方は止める。AIは出せない（確認は人がする）。

取り消しは、元の記録を指して前の状態へ戻す記録を足す（reverts_record_id）。戻す権限は元の移り方と同じにする。
"""

from typing import Literal

from pydantic import Field
from sqlalchemy import func, select

from v3server.canonical_tables.table_base import new_id
from v3server.canonical_tables.translation_review_import_tables import (
    ReviewRecord,
    ReviewState,
)
from v3server.canonical_tables.work_tree_tables import Page
from v3server.operations.operation_base import (
    OpBase,
    Scope,
    get_in_work,
    page_obj,
    work_obj,
)
from v3server.v3_error_types import Invalid

ReviewStatus = Literal["draft", "in_review", "approved", "needs_changes"]
REVIEW_STATUSES: tuple[str, ...] = ("draft", "in_review", "approved", "needs_changes")

# (前, 後) → 出す側か決める側か
SUBMIT_MOVES = {("draft", "in_review"), ("needs_changes", "in_review"), ("in_review", "draft")}
DECIDE_MOVES = {("in_review", "approved"), ("in_review", "needs_changes"), ("approved", "draft")}


def move_kind(before: str, after: str) -> Literal["submit", "decide"]:
    if (before, after) in SUBMIT_MOVES:
        return "submit"
    if (before, after) in DECIDE_MOVES:
        return "decide"
    raise Invalid(f"{before} から {after} へは移せない")


async def current_status(session, target_kind: str, target_id: str) -> str:
    row = (await session.execute(select(ReviewState).where(
        ReviewState.target_kind == target_kind, ReviewState.target_id == target_id))).scalar()
    return row.status if row else "draft"


class SetReviewStatus(OpBase):
    type: Literal["set_review_status"] = "set_review_status"
    target_kind: Literal["page", "work"]
    # 作品のときは作品の id
    target_id: str
    status: ReviewStatus
    comment: str | None = None
    # 取り消しのときだけ。戻す元の記録
    reverts_record_id: str | None = None
    record_id: str = Field(default_factory=new_id)

    async def _move(self, session, work) -> tuple[str, str]:
        """(前の状態, 権限を決める移り方)。取り消しは元の記録の移り方で決める。"""
        before = await current_status(session, self.target_kind, self.target_id)
        if self.reverts_record_id is None:
            return before, move_kind(before, self.status)
        rec = await get_in_work(session, ReviewRecord, self.reverts_record_id, work.id)
        if (rec.target_kind, rec.target_id) != (self.target_kind, self.target_id):
            raise Invalid("取り消す記録の対象が違う")
        if rec.to_status != before or rec.from_status != self.status:
            raise Invalid("取り消す記録のあとに状態が変わっている。今の状態から移し直す")
        # 取り消しの取り消しもあるので、取り消しでない元の記録までたどる
        root = rec
        while root.reverts_record_id is not None:
            root = await session.get(ReviewRecord, root.reverts_record_id)
        return before, move_kind(root.from_status, root.to_status)

    async def scope(self, session, work):
        if self.target_kind == "page":
            page = await get_in_work(session, Page, self.target_id, work.id)
            if page.removed:
                raise Invalid("抜いたページの状態は変えない")
        elif self.target_id != work.id:
            raise Invalid("作品の状態は、その作品の id を target_id に渡す")
        _, kind = await self._move(session, work)
        if kind == "decide":
            return Scope("can_approve", work_obj(work.id))
        if self.target_kind == "page":
            return Scope("can_draw", page_obj(self.target_id))
        return Scope("can_manage", work_obj(work.id))

    async def apply(self, ctx):
        session = ctx.session
        before, _ = await self._move(session, ctx.work)
        if self.reverts_record_id is None and self.status == "needs_changes" and not (self.comment or "").strip():
            raise Invalid("直しが要るにするときは、何を直すかをコメントに書く")
        row = (await session.execute(select(ReviewState).where(
            ReviewState.target_kind == self.target_kind, ReviewState.target_id == self.target_id))).scalar()
        if row is None:
            session.add(ReviewState(work_id=ctx.work.id, target_kind=self.target_kind, target_id=self.target_id,
                                    status=self.status, updated_by=ctx.actor.id))
        else:
            row.status = self.status
            row.updated_by = ctx.actor.id
            row.updated_at = func.now()
        session.add(ReviewRecord(
            id=self.record_id, work_id=ctx.work.id, target_kind=self.target_kind, target_id=self.target_id,
            from_status=before, to_status=self.status, comment=self.comment, actor_kind=ctx.actor.kind,
            actor_id=ctx.actor.id, reverts_record_id=self.reverts_record_id))
        # 取り消しも、取り消しの取り消しも、この記録を指して前の状態へ戻す（記録はどれも残る）
        return {"type": self.type, "target_kind": self.target_kind, "target_id": self.target_id,
                "status": before, "comment": "取り消し", "reverts_record_id": self.record_id}
