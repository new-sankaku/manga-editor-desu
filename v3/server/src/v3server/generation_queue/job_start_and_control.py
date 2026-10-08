"""依頼を受ける・取り消す・続ける。画面（API）とロックの取り返しから呼ぶ。"""

import asyncio
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client, WithStartWorkflowOperation, WorkflowUpdateRPCTimeoutOrCancelledError
from temporalio.common import WorkflowIDConflictPolicy
from temporalio.service import RPCError, RPCStatusCode

from v3server.allowed_destinations import is_allowed
from sqlalchemy import select

from v3server.canonical_tables.service_and_job_tables import Job, ProcessRoute, Service, ServiceProcess
from v3server.canonical_tables.work_tree_tables import Page, Work
from v3server.generation_queue.generation_workflow import GenerationJob, JobInput
from v3server.generation_queue.queue_names_and_priority import (
    CONTROL_QUEUE,
    QUEUE_ENTRY_WAIT,
    job_priority,
)
from v3server.generation_queue.input_image_preparation import prepare_input_images
from v3server.generation_queue.known_processes import check_process_task
from v3server.openfga_permissions import Authz
from v3server.operations.ai_involvement import require_ai_may
from v3server.operations.operation_base import get_in_work, page_obj, work_obj
from v3server.request_actor import Actor
from v3server.v3_error_types import Forbidden, Invalid, NotFound, QueueNotRunning


def workflow_id(job_id: str) -> str:
    return f"job-{job_id}"


async def enqueue(
    session: AsyncSession,
    authz: Authz,
    temporal: Client,
    actor: Actor,
    work_id: str,
    process: str,
    request: dict[str, Any],
    requested_via: Literal["human", "ai"],
    page_id: str | None = None,
    service_id: str | None = None,
) -> Job:
    """処理ごとの送り先（ProcessRoute）へ1件頼む。送り先は人が決めたものだけを使う。
    service_id を渡すと、その処理を受けられる別のつなぎ先へ送る（画面でつなぎ先を選ぶ）。その先も送ってよい先の決まりにかける。
    何の作業の処理か（ai_task・ai_action）は送り先（ProcessRoute）から読む。"""
    if page_id is not None:
        await get_in_work(session, Page, page_id, work_id)
        relation, obj = "can_draw", page_obj(page_id)
    else:
        relation, obj = "can_manage", work_obj(work_id)
    if not await authz.check(actor.permission_user, relation, obj):
        raise Forbidden(f"{actor.permission_user} に {obj} の {relation} が無い")

    route = await session.get(ProcessRoute, process)
    if route is None:
        raise Invalid(f"{process} の送り先が決まっていない")
    if route.ai_task is None or route.ai_action is None:
        raise Invalid(f"{process} が何の作業の処理か（ai_task・ai_action）が決まっていない")
    check_process_task(process, route.ai_task, route.ai_action)
    # 頼んだのが人でもAIでも、処理をするのはAI。作業のAIの関与で許されていなければ受けない
    require_ai_may(await session.get(Work, work_id), route.ai_task, route.ai_action)
    request = await prepare_input_images(session, work_id, request)
    service = await session.get(Service, service_id or route.service_id)
    if service is None:
        raise NotFound(f"services:{service_id}")
    if service_id is not None and await session.scalar(select(ServiceProcess.id).where(
            ServiceProcess.service_id == service.id, ServiceProcess.process == process)) is None:
        raise Invalid(f"{service.name} は {process} を受けられない（先に処理の中身を登録する）")
    if not await is_allowed(session, work_id, service):
        # 別の先へは回さない。人が送ってよい先に足すか、送り先を変える
        raise Forbidden(f"{service.name} はこの作品の送ってよい先に無い")

    job = Job(
        work_id=work_id,
        service_id=service.id,
        process=process,
        page_id=page_id,
        requested_by=actor.permission_user,
        requested_via=requested_via,
        request=request,
    )
    session.add(job)
    await session.flush()
    job.workflow_id = workflow_id(job.id)
    await session.commit()
    await session.refresh(job)

    await _start_and_wait_until_queued(session, temporal, job, JobInput(
        job.id, work_id, service.id, requested_via, route.resend_limit))
    return job


async def _start_and_wait_until_queued(session: AsyncSession, temporal: Client, job: Job, inp: JobInput) -> None:
    """流れを始め、送信をつなぎ先の待ち行列に入れ終えるまで待つ（generation_workflow.py の until_queued）。
    入れ終えてから返すので、続けて頼んだ依頼は頼んだ順に待ち行列に入る（V3細部の決めごと 4.4「同じ扱いの中は、頼んだ順」）。
    流れを始めただけで返すと、続けて頼んだ依頼の送信が前後して入った（2026-10-08 実測。V3サーバーの土台 7章）。
    制御の作業者が動いておらず QUEUE_ENTRY_WAIT を超えたら、流れを終わらせ、依頼を止めて知らせる。"""
    start = WithStartWorkflowOperation(
        GenerationJob.run,
        inp,
        id=job.workflow_id,
        task_queue=CONTROL_QUEUE,
        id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
        priority=job_priority(inp.requested_via, inp.work_id),
    )
    limit = asyncio.timeout(QUEUE_ENTRY_WAIT.total_seconds())
    try:
        async with limit:
            await temporal.execute_update_with_start_workflow(GenerationJob.until_queued, start_workflow_operation=start)
    except (TimeoutError, WorkflowUpdateRPCTimeoutOrCancelledError) as e:
        # 時間を超えて待つのを止めると、Temporal の SDK は CancelledError を
        # WorkflowUpdateRPCTimeoutOrCancelledError に変えて投げる。時間を超えたときだけここで扱う
        if not limit.expired():
            raise
        detail = f"{QUEUE_ENTRY_WAIT.total_seconds():.0f} 秒待っても待ち行列に入らなかった（制御の作業者が動いていない）"
        try:
            await temporal.get_workflow_handle(job.workflow_id).terminate(detail)
        except RPCError as not_started:
            # 流れが始まる前に時間を超えた。終わらせる流れが無い
            if not_started.status != RPCStatusCode.NOT_FOUND:
                raise
        job.status, job.failure_kind, job.failure_detail = "stopped", "queue_not_running", detail
        await session.commit()
        raise QueueNotRunning(f"jobs:{job.id} {detail}") from e


async def cancel(temporal: Client, job: Job) -> None:
    if job.workflow_id is None:
        raise NotFound(f"jobs:{job.id} は流れていない")
    await temporal.get_workflow_handle(job.workflow_id).cancel()


async def resume(temporal: Client, job: Job) -> None:
    if job.status != "waiting_budget":
        raise Invalid("予算の上限で待っているものだけ続けられる")
    await temporal.get_workflow_handle(job.workflow_id).signal(GenerationJob.resume)
