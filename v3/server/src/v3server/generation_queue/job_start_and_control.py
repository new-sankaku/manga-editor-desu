"""依頼を受ける・取り消す・続ける。画面（API）とロックの取り返しから呼ぶ。"""

from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client

from v3server.allowed_destinations import is_allowed
from v3server.canonical_tables.service_and_job_tables import Job, ProcessRoute, Service
from v3server.canonical_tables.work_tree_tables import Page, Work
from v3server.generation_queue.generation_workflow import GenerationJob, JobInput
from v3server.generation_queue.queue_names_and_priority import (
    CONTROL_QUEUE,
    job_priority,
)
from v3server.generation_queue.input_image_preparation import prepare_input_images
from v3server.openfga_permissions import Authz
from v3server.operations.ai_involvement import require_ai_may
from v3server.operations.operation_base import get_in_work, page_obj, work_obj
from v3server.request_actor import Actor
from v3server.v3_error_types import Forbidden, Invalid, NotFound


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
) -> Job:
    """処理ごとの送り先（ProcessRoute）へ1件頼む。送り先は人が決めたものだけを使う。"""
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
    # 頼んだのが人でもAIでも、処理をするのはAI。作業のAIの関与で許されていなければ受けない
    require_ai_may(await session.get(Work, work_id), route.ai_task, route.ai_action)
    request = await prepare_input_images(session, work_id, request)
    service = await session.get(Service, route.service_id)
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

    await temporal.start_workflow(
        GenerationJob.run,
        JobInput(job.id, work_id, service.id, requested_via, route.resend_limit),
        id=job.workflow_id,
        task_queue=CONTROL_QUEUE,
        priority=job_priority(requested_via, work_id),
    )
    return job


async def cancel(temporal: Client, job: Job) -> None:
    if job.workflow_id is None:
        raise NotFound(f"jobs:{job.id} は流れていない")
    await temporal.get_workflow_handle(job.workflow_id).cancel()


async def resume(temporal: Client, job: Job) -> None:
    if job.status != "waiting_budget":
        raise Invalid("予算の上限で待っているものだけ続けられる")
    await temporal.get_workflow_handle(job.workflow_id).signal(GenerationJob.resume)
