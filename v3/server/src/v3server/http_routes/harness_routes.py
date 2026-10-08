"""AIハーネスの口（llm_doc/V3ハーネスの実装.md 6章）。

工程を始める・今の状態（snapshot）・作業の中身・人の操作（Update を流れへ渡す）・確認待ちの一覧・生の状態（SSE）。
人の操作の可否は流れの側の検証（validator）が決める。断られたら 409 で理由を返す。
"""

from typing import Any, Literal

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from temporalio.client import WorkflowUpdateFailedError
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError, RPCStatusCode

from v3server.canonical_tables.harness_tables import HarnessStageRun, HarnessStaleMark, HarnessUnit
from v3server.canonical_tables.work_tree_tables import Episode
from v3server.harness import live_stream
from v3server.harness.harness_limits import StageLimits, check_completion
from v3server.harness.harness_record import add_event, now, patch_stage
from v3server.harness.harness_states import STAGES, UNIT_KIND_OF_STAGE
from v3server.harness.name_draft_steps import NameSpec
from v3server.harness.panel_drawing_steps import DrawingSpec
from v3server.harness.review_list import KINDS, review_items
from v3server.harness.stage_workflow import HARNESS_QUEUE, Rerun, StageControl, StageInput, StageWorkflow, stage_workflow_id
from v3server.harness.unit_workflow import Control, LimitChange, Review, WorkUnitWorkflow
from v3server.http_routes.http_dependencies import ActorDep, AuthzDep, SessionDep, TemporalDep, require
from v3server.operations.operation_base import get_in_work, work_obj
from v3server.v3_error_types import Invalid, Locked, NotFound

router = APIRouter()

SPEC_MODELS = {"name_draft": ("name", NameSpec), "panel_drawing": ("drawing", DrawingSpec)}


class StartStage(BaseModel):
    episode_id: str
    stage: Literal["S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7"]
    limits: StageLimits
    # 作業の中身の決めごと。{"name": NameSpec, "drawing": DrawingSpec}。始める工程と、その後の工程の分を渡す
    spec: dict[str, Any] = Field(default_factory=dict)


class UnitControlBody(BaseModel):
    action: Literal["pause", "resume", "cancel_step", "cancel_unit"]
    mode: Literal["now", "boundary"] | None = None


class ReviewBody(BaseModel):
    action: Literal["approve", "reject", "edit"]
    candidate_id: str | None = None
    image_id: str | None = None
    reason: str | None = None


class LimitsBody(BaseModel):
    limits: dict[str, Any]


class StageControlBody(BaseModel):
    action: Literal["pause", "resume", "cancel"]


class RerunBody(BaseModel):
    unit_ids: list[str] = Field(min_length=1)


def _check_spec(stage: str, spec: dict[str, Any]) -> None:
    unknown = set(spec) - {key for key, _ in SPEC_MODELS.values()}
    if unknown:
        raise Invalid(f"知らない決めごと: {sorted(unknown)}")
    for i, s in enumerate(STAGES):
        kind = UNIT_KIND_OF_STAGE.get(s)
        if kind is None or i < STAGES.index(stage):
            continue
        key, model = SPEC_MODELS[kind]
        if key not in spec:
            if s == stage:
                raise Invalid(f"{stage} を始めるには spec.{key} が要る")
            continue
        model.model_validate(spec[key])


async def _call(fn):
    """流れへの Update。検証で断られたら 409、流れが無ければ 404。"""
    try:
        return await fn()
    except WorkflowUpdateFailedError as e:
        cause = e.cause
        raise Locked(getattr(cause, "message", None) or str(cause)) from e
    except RPCError as e:
        if e.status == RPCStatusCode.NOT_FOUND:
            raise NotFound("流れが動いていない（終わったか、まだ始まっていない）") from e
        raise


@router.post("/works/{work_id}/harness/stages", status_code=201)
async def start_stage(work_id: str, body: StartStage, session: SessionDep, authz: AuthzDep, temporal: TemporalDep,
                      actor: ActorDep):
    await require(authz, actor, "can_manage", work_obj(work_id))
    if actor.kind != "human":
        raise Invalid("工程は人が始める")
    await get_in_work(session, Episode, body.episode_id, work_id)
    try:
        check_completion(body.limits.completion)
        _check_spec(body.stage, body.spec)
    except ValueError as e:
        raise Invalid(str(e)) from e
    run = HarnessStageRun(work_id=work_id, episode_id=body.episode_id, stage=body.stage, status="queued",
                          requested_by=actor.id, limits=body.limits.model_dump(), spec=body.spec,
                          workflow_id=stage_workflow_id(body.episode_id))
    session.add(run)
    await session.flush()
    await patch_stage(session, run.id, {})
    try:
        await temporal.start_workflow(StageWorkflow.run, StageInput(run.id, run.limits), id=run.workflow_id,
                                      task_queue=HARNESS_QUEUE)
    except WorkflowAlreadyStartedError as e:
        await session.rollback()
        raise Locked("この話の工程の進行役はもう動いている（取り消してから始める）") from e
    await session.commit()
    return {"stage_run_id": run.id, "workflow_id": run.workflow_id}


@router.get("/works/{work_id}/harness/snapshot")
async def get_snapshot(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep,
                       unit_id: str | None = None):
    await require(authz, actor, "can_view", work_obj(work_id))
    if unit_id is not None:
        await get_in_work(session, HarnessUnit, unit_id, work_id)
    return await live_stream.snapshot(session, work_id, unit_id)


@router.get("/works/{work_id}/harness/units/{unit_id}")
async def get_unit(work_id: str, unit_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    await get_in_work(session, HarnessUnit, unit_id, work_id)
    return await live_stream.unit_detail(session, unit_id)


async def _unit_handle(session, temporal, work_id: str, unit_id: str):
    unit = await get_in_work(session, HarnessUnit, unit_id, work_id)
    return temporal.get_workflow_handle(unit.workflow_id)


@router.post("/works/{work_id}/harness/units/{unit_id}/control")
async def unit_control(work_id: str, unit_id: str, body: UnitControlBody, session: SessionDep, authz: AuthzDep,
                       temporal: TemporalDep, actor: ActorDep):
    await require(authz, actor, "can_manage", work_obj(work_id))
    handle = await _unit_handle(session, temporal, work_id, unit_id)
    return await _call(lambda: handle.execute_update(WorkUnitWorkflow.control,
                                                     Control(body.action, actor.id, body.mode)))


@router.post("/works/{work_id}/harness/units/{unit_id}/review")
async def unit_review(work_id: str, unit_id: str, body: ReviewBody, session: SessionDep, authz: AuthzDep,
                      temporal: TemporalDep, actor: ActorDep):
    await require(authz, actor, "can_manage", work_obj(work_id))
    if actor.kind != "human":
        raise Invalid("判断は人がする")
    handle = await _unit_handle(session, temporal, work_id, unit_id)
    return await _call(lambda: handle.execute_update(WorkUnitWorkflow.review, Review(
        body.action, actor.id, body.candidate_id, body.image_id, body.reason)))


@router.post("/works/{work_id}/harness/units/{unit_id}/limits")
async def unit_limits(work_id: str, unit_id: str, body: LimitsBody, session: SessionDep, authz: AuthzDep,
                      temporal: TemporalDep, actor: ActorDep):
    await require(authz, actor, "can_manage", work_obj(work_id))
    handle = await _unit_handle(session, temporal, work_id, unit_id)
    return await _call(lambda: handle.execute_update(WorkUnitWorkflow.set_limits, LimitChange(actor.id, body.limits)))


async def _stage_handle(session, temporal, work_id: str, stage_run_id: str):
    run = await get_in_work(session, HarnessStageRun, stage_run_id, work_id)
    if run.status in ("done", "cancelled"):
        raise Locked(f"この工程の実行は終わっている（{run.status}）")
    return temporal.get_workflow_handle(run.workflow_id)


@router.post("/works/{work_id}/harness/stages/{stage_run_id}/control")
async def stage_control(work_id: str, stage_run_id: str, body: StageControlBody, session: SessionDep,
                        authz: AuthzDep, temporal: TemporalDep, actor: ActorDep):
    await require(authz, actor, "can_manage", work_obj(work_id))
    handle = await _stage_handle(session, temporal, work_id, stage_run_id)
    return await _call(lambda: handle.execute_update(StageWorkflow.control, StageControl(body.action, actor.id)))


@router.post("/works/{work_id}/harness/stages/{stage_run_id}/approve")
async def stage_approve(work_id: str, stage_run_id: str, session: SessionDep, authz: AuthzDep,
                        temporal: TemporalDep, actor: ActorDep):
    await require(authz, actor, "can_manage", work_obj(work_id))
    if actor.kind != "human":
        raise Invalid("工程の承認は人がする")
    handle = await _stage_handle(session, temporal, work_id, stage_run_id)
    return await _call(lambda: handle.execute_update(StageWorkflow.approve, actor.id))


@router.post("/works/{work_id}/harness/stages/{stage_run_id}/rerun")
async def stage_rerun(work_id: str, stage_run_id: str, body: RerunBody, session: SessionDep, authz: AuthzDep,
                      temporal: TemporalDep, actor: ActorDep):
    """古くなった作業を作り直す（人が頼んだときだけ。上流の変化で自動では動かさない）。"""
    await require(authz, actor, "can_manage", work_obj(work_id))
    handle = await _stage_handle(session, temporal, work_id, stage_run_id)
    return await _call(lambda: handle.execute_update(StageWorkflow.rerun, Rerun(actor.id, body.unit_ids)))


@router.post("/works/{work_id}/harness/stale/{mark_id}/dismiss")
async def dismiss_stale(work_id: str, mark_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    """古い印を「このままでよい」で閉じる。"""
    await require(authz, actor, "can_manage", work_obj(work_id))
    mark = await get_in_work(session, HarnessStaleMark, mark_id, work_id)
    if mark.status != "open":
        raise Locked(f"もう閉じている（{mark.status}）")
    mark.status, mark.resolved_at = "dismissed", now()
    unit = await session.get(HarnessUnit, mark.unit_id)
    await add_event(session, work_id, "stale_resolved", {"mark_id": mark.id, "unit_id": unit.id, "status": "dismissed",
                                                         "by": actor.id}, unit.stage_run_id, unit.id)
    await session.commit()
    return {"id": mark.id, "status": mark.status}


@router.get("/works/{work_id}/harness/review-items")
async def get_review_items(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep,
                           kind: list[str] | None = Query(default=None), stage: str | None = None,
                           page_id: str | None = None, stage_run_id: str | None = None):
    await require(authz, actor, "can_view", work_obj(work_id))
    try:
        items = await review_items(session, work_id, kind, stage, page_id, stage_run_id)
    except ValueError as e:
        raise Invalid(f"{e}（{', '.join(KINDS)}）") from e
    return {"items": items}


@router.get("/works/{work_id}/harness/stream")
async def get_stream(work_id: str, request: Request, authz: AuthzDep, actor: ActorDep,
                     after: int | None = None, last_event_id: str | None = Header(default=None)):
    """SSE。Last-Event-ID（か ?after=）の続きから流す。画面は fetch で読む（見出しで名乗るため EventSource は使わない）。"""
    await require(authz, actor, "can_view", work_obj(work_id))
    start = after if after is not None else int(last_event_id) if last_event_id else 0
    return StreamingResponse(live_stream.stream(work_id, start, request.is_disconnected),
                             media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/works/{work_id}/harness/stage-runs")
async def list_stage_runs(work_id: str, session: SessionDep, authz: AuthzDep, actor: ActorDep):
    await require(authz, actor, "can_view", work_obj(work_id))
    runs = (await session.execute(select(HarnessStageRun).where(HarnessStageRun.work_id == work_id)
                                  .order_by(HarnessStageRun.created_at))).scalars().all()
    return {"stage_runs": [live_stream.row_of(r, live_stream.STAGE_FIELDS) for r in runs]}
