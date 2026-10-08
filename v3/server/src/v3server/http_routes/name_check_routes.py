"""ネームの検査を回す口。今のページとコマも、採用する前の案も、同じ検査にかける（人が作ってもAIが作っても同じ）。

閾値は作品の Threshold の表から、ネームの検査の鍵の行だけを読む。値の形は {"value": 数}。
検証の状態が rejected の行は使わない。unverified の行は使い、結果に状態を添える（V3ハーネス設計 7章）。"""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from v3server.canonical_tables.check_result_tables import NameCheckRun
from v3server.canonical_tables.name_proposal_tables import NameProposal
from v3server.canonical_tables.threshold_and_finding_tables import Threshold
from v3server.canonical_tables.work_tree_tables import Episode, Work
from v3server.http_routes.http_dependencies import (
    ActorDep,
    AuthzDep,
    SessionDep,
    require,
    row,
)
from v3server.name_checks.name_check_runner import ALL_THRESHOLD_KEYS, run_name_checks
from v3server.operations.name_draft_conversion import (
    name_draft_of_episode,
    name_draft_of_proposal,
)
from v3server.operations.operation_base import get_in_work, work_obj
from v3server.v3_error_types import Invalid

router = APIRouter()

RUN_FIELDS = ("id", "episode_id", "proposal_id", "run_by_kind", "run_by_id", "thresholds_used", "report", "created_at")


class NameCheckRequest(BaseModel):
    # 案を検査するときだけ渡す。無ければ今のページとコマを検査する
    proposal_id: str | None = None


async def name_check_thresholds(session, work_id: str) -> tuple[dict[str, float], dict[str, dict]]:
    rows = (await session.execute(select(Threshold).where(
        Threshold.work_id == work_id, Threshold.key.in_(list(ALL_THRESHOLD_KEYS))))).scalars().all()
    values, used = {}, {}
    for t in rows:
        if t.status == "rejected":
            continue
        if set(t.value) != {"value"} or not isinstance(t.value["value"], (int, float)):
            raise Invalid(f"閾値 {t.key} の値の形が {{'value': 数}} でない: {t.value}")
        values[t.key] = float(t.value["value"])
        used[t.key] = {"value": t.value["value"], "source": t.source, "status": t.status}
    return values, used


@router.get("/name-checks/threshold-keys")
async def threshold_keys(actor: ActorDep):
    """ネームの検査が読む閾値の鍵と意味。"""
    return ALL_THRESHOLD_KEYS


@router.post("/works/{work_id}/episodes/{episode_id}/name-checks", status_code=201)
async def run_checks(work_id: str, episode_id: str, body: NameCheckRequest, session: SessionDep, authz: AuthzDep,
                     actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    await get_in_work(session, Episode, episode_id, work_id)
    work = await session.get(Work, work_id)
    if body.proposal_id is None:
        draft = await name_draft_of_episode(session, work, episode_id)
    else:
        prop = await get_in_work(session, NameProposal, body.proposal_id, work_id)
        if prop.episode_id != episode_id:
            raise Invalid("案の話が合わない")
        draft = name_draft_of_proposal(work, prop.pages)
    values, used = await name_check_thresholds(session, work_id)
    report = run_name_checks(draft, values)
    run = NameCheckRun(work_id=work_id, episode_id=episode_id, proposal_id=body.proposal_id, run_by_kind=actor.kind,
                       run_by_id=actor.id, thresholds_used=used, report=report.model_dump())
    session.add(run)
    await session.commit()
    return row(run, *RUN_FIELDS)


@router.get("/works/{work_id}/episodes/{episode_id}/name-checks")
async def list_checks(work_id: str, episode_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    q = select(NameCheckRun).where(NameCheckRun.work_id == work_id, NameCheckRun.episode_id == episode_id)
    return [row(r, *RUN_FIELDS) for r in (await session.execute(q.order_by(NameCheckRun.created_at))).scalars()]
