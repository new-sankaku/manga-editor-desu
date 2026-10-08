"""作品と話の進み具合（V3点検の結果 5章の6・V3細部の決めごと 19章）。

- 話ごと：状態ごとのページの数、確認待ちのページ、締切
- 見込み（未検証）：この作品で1枚にかかった時間 =（今 − 作品を作った時）÷ 承認したページの数。
  話の残りのページ（承認していないページ）を番号の順に1枚ずつ足して、それぞれの終わる時を出す。
  締切より後になるページに印を付ける。待ち行列の時間（19章）はまだ入れていない。
  承認したページが無い作品では、1枚の時間を出せないので見込みは出さない（理由を返す）。当たるかは作ってみるまで未検証
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from v3server.canonical_tables.translation_review_import_tables import ReviewState
from v3server.canonical_tables.work_tree_tables import Episode, Page, Work
from v3server.operations.review_operations import REVIEW_STATUSES

ESTIMATE_NOTE = ("未検証。1枚の時間は（今 − 作品を作った時）÷ 承認したページの数。待ち行列の時間は入れていない")


@dataclass
class PageStatus:
    id: str
    number: int
    status: str


def estimate(now: datetime, work_created_at: datetime, approved_in_work: int, remaining: list[PageStatus],
             deadline: datetime | None) -> dict[str, Any]:
    """話の見込み。remaining は承認していないページ（番号の順）。"""
    if approved_in_work == 0:
        return {"per_page_seconds": None, "projected_finish": None, "on_track": None, "late_page_ids": [],
                "reason": "この作品で承認したページがまだ無いので、1枚にかかる時間を出せない", "note": ESTIMATE_NOTE}
    per_page = (now - work_created_at) / approved_in_work
    finishes = [(p, now + per_page * (n + 1)) for n, p in enumerate(remaining)]
    projected = finishes[-1][1] if finishes else now
    late = [p.id for p, t in finishes if deadline is not None and t > deadline]
    return {"per_page_seconds": per_page / timedelta(seconds=1), "projected_finish": projected,
            "on_track": None if deadline is None else projected <= deadline, "late_page_ids": late, "reason": None,
            "note": ESTIMATE_NOTE}


async def work_progress(session: AsyncSession, work: Work, now: datetime) -> dict[str, Any]:
    states = {(r.target_kind, r.target_id): r.status for r in (await session.execute(
        select(ReviewState).where(ReviewState.work_id == work.id))).scalars()}
    episodes = (await session.execute(select(Episode).where(
        Episode.work_id == work.id, Episode.removed.is_(False)).order_by(Episode.number))).scalars().all()
    pages = (await session.execute(select(Page).where(
        Page.work_id == work.id, Page.removed.is_(False)).order_by(Page.number))).scalars().all()
    by_episode: dict[str, list[PageStatus]] = {}
    for p in pages:
        by_episode.setdefault(p.episode_id, []).append(PageStatus(p.id, p.number, states.get(("page", p.id), "draft")))
    approved_in_work = sum(1 for ps in by_episode.values() for p in ps if p.status == "approved")
    out = []
    for ep in episodes:
        ps = by_episode.get(ep.id, [])
        counts = {s: sum(1 for p in ps if p.status == s) for s in REVIEW_STATUSES}
        remaining = [p for p in ps if p.status != "approved"]
        out.append({
            "episode_id": ep.id, "number": ep.number, "title": ep.title, "deadline": ep.deadline,
            "page_count": len(ps), "pages_by_status": counts,
            "pending_review_page_ids": [p.id for p in ps if p.status == "in_review"],
            "needs_changes_page_ids": [p.id for p in ps if p.status == "needs_changes"],
            "overdue": ep.deadline is not None and ep.deadline < now and bool(remaining),
            "estimate": estimate(now, work.created_at, approved_in_work, remaining, ep.deadline),
        })
    return {"work_id": work.id, "work_status": states.get(("work", work.id), "draft"),
            "approved_pages_in_work": approved_in_work, "episodes": out}
