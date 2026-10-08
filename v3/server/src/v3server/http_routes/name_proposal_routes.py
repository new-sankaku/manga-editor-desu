"""ネームの案を見る口と、今のネームを形にして返す口。案を出す・採用するのは操作（/works/{id}/ops）で行う。"""

from fastapi import APIRouter
from sqlalchemy import select

from v3server.canonical_tables.name_proposal_tables import NameProposal
from v3server.canonical_tables.work_tree_tables import Episode, Work
from v3server.http_routes.http_dependencies import (
    ActorDep,
    AuthzDep,
    SessionDep,
    require,
    row,
)
from v3server.operations.name_draft_conversion import name_draft_of_episode
from v3server.operations.operation_base import get_in_work, work_obj

router = APIRouter()

PROPOSAL_FIELDS = ("id", "episode_id", "made_by", "submitted_by_kind", "submitted_by_id", "job_id", "pages", "note",
                   "status", "created_at")


@router.get("/works/{work_id}/episodes/{episode_id}/name-proposals")
async def list_name_proposals(work_id: str, episode_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    await get_in_work(session, Episode, episode_id, work_id)
    q = select(NameProposal).where(NameProposal.episode_id == episode_id).order_by(NameProposal.created_at)
    return [row(p, *PROPOSAL_FIELDS) for p in (await session.execute(q)).scalars()]


@router.get("/works/{work_id}/episodes/{episode_id}/name-draft")
async def get_name_draft(work_id: str, episode_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """今のページとコマを、ネームの形（name_structure の NameDraft）で返す。誰が作ったかに依らず同じ形。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    await get_in_work(session, Episode, episode_id, work_id)
    work = await session.get(Work, work_id)
    return (await name_draft_of_episode(session, work, episode_id)).model_dump()
