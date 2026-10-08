"""Temporal の活動。正本（PostgreSQL）を読み書きするのはここだけ。"""

import asyncio
import time
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from temporalio import activity
from temporalio.exceptions import ApplicationError

from v3server.allowed_destinations import is_allowed
from v3server.canonical_tables.service_and_job_tables import (
    CallLog,
    Job,
    Service,
    ServiceProcess,
)
from v3server.database_engine import get_sessionmaker
from v3server.generation_queue.known_processes import KNOWN_PROCESSES, handle_known_result
from v3server.image_intake import take_in_image
from v3server.llm_questions.answer_json_reader import BrokenAnswerError
from v3server.openfga_permissions import Authz, open_authz
from v3server.operations.image_file_operations import RegisterImage
from v3server.operations.operation_submit_and_undo import submit
from v3server.request_actor import Actor
from v3server.service_senders.sender_by_adapter_name import ADAPTERS
from v3server.service_senders.sender_result_types import AdapterError
from v3server.v3_error_types import V3Error

# ここに載った種類は、活動の中では送り直さない（workflows.py が種類ごとに扱う）
NON_RETRYABLE = ["rate_limited", "refused", "broken_response", "interrupted", "budget", "destination_not_allowed"]

# 活動の生存を Temporal に知らせる間隔（秒）。取り消しは、この知らせの返事で活動に届く
HEARTBEAT_SECONDS = 5

_authz: Authz | None = None


async def _get_authz() -> Authz:
    global _authz
    if _authz is None:
        async with get_sessionmaker()() as session:
            _authz = await open_authz(session)
    return _authz


async def _heartbeat_forever() -> None:
    while True:
        activity.heartbeat()
        await asyncio.sleep(HEARTBEAT_SECONDS)


async def _register_images(session, job: Job, service: Service, result) -> list[dict]:
    """受け取った絵を置き場に置き、AI の操作として登録する（操作の窓口 submit を通す）。
    依頼した人の権限で動く。登録の引数は job.request["register"]（comfyui_sender.py の docstring）。"""
    register = job.request["register"]
    actor = Actor(kind="ai", id=f"service:{service.id}", on_behalf_of=job.requested_by)
    authz = await _get_authz()
    registered = []
    inputs = [e["image_id"] for e in job.request.get("prepared_inputs", []) if e.get("image_id")]
    for data in result.image_files:
        # 生成の出口も、人の絵と同じ入口を通す（規制の判定を差し込む場所。V3ハーネス設計 12章）
        stored = await take_in_image(session, job.work_id, data, "generated")
        op = RegisterImage(
            role=register["role"], origin="generated", page_id=register.get("page_id"),
            panel_id=register.get("panel_id"), job_id=job.id, based_on_image_id=register.get("based_on_image_id"),
            sha256=stored.sha256, media_type=stored.media_type, width=stored.width, height=stored.height,
            dpi=stored.dpi, details={"input_image_ids": inputs} if inputs else {},
        )
        await submit(session, authz, actor, job.work_id, op)
        registered.append({"image_id": op.id, "sha256": stored.sha256})
    return registered


async def _month_cost(session, service_id: str) -> Decimal:
    start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = await session.scalar(
        select(func.coalesce(func.sum(CallLog.cost), 0)).where(
            CallLog.service_id == service_id, CallLog.created_at >= start
        )
    )
    return Decimal(total)


@activity.defn
async def call_service(job_id: str) -> None:
    attempt = activity.info().attempt
    async with get_sessionmaker()() as session:
        job = await session.get(Job, job_id)
        service = await session.get(Service, job.service_id)
        sp = (
            await session.execute(
                select(ServiceProcess).where(
                    ServiceProcess.service_id == service.id, ServiceProcess.process == job.process
                )
            )
        ).scalar_one_or_none()

        def log(outcome: str, kind: str | None = None, detail: str | None = None, **kw) -> None:
            session.add(
                CallLog(job_id=job.id, work_id=job.work_id, service_id=service.id, attempt=attempt,
                        outcome=outcome, failure_kind=kind, detail=detail, **kw)
            )

        async def stop(kind: str, detail: str, retry_after: float | None = None):
            log("blocked" if kind in ("destination_not_allowed", "budget") else "failed", kind, detail)
            await session.commit()
            raise ApplicationError(detail, {"retry_after": retry_after}, type=kind, non_retryable=kind in NON_RETRYABLE)

        # 送る直前にもう一度確かめる。待っている間に送ってよい先から外されたかもしれない
        if not await is_allowed(session, job.work_id, service):
            await stop("destination_not_allowed", f"{service.name} はこの作品の送ってよい先に無い")
        if sp is None:
            await stop("refused", f"{service.name} は {job.process} を受けられない")
        if service.monthly_budget is not None and await _month_cost(session, service.id) >= service.monthly_budget:
            await stop("budget", f"{service.name} の月の予算の上限に達した")

        job.status = "running"
        await session.commit()

        started = time.monotonic()
        # 送っている間も生存を知らせる。人が取り消すと、その返事で CancelledError がここに届き、
        # 送り手（comfyui_sender.py）が送り先の物を止める
        heartbeat = asyncio.create_task(_heartbeat_forever())
        try:
            result = await ADAPTERS[service.adapter](service, sp, job.request)
        except AdapterError as e:
            await stop(e.kind, e.detail, e.retry_after)
        finally:
            heartbeat.cancel()
        duration_ms = int((time.monotonic() - started) * 1000)

        log(
            "ok",
            model=result.model,
            settings=result.settings,
            seed=result.seed,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost=sp.cost_per_call,
            duration_ms=duration_ms,
        )
        await session.commit()

        output = dict(result.output)
        if result.image_files:
            # 呼び出しは成功している。絵の登録を断られたら（ロック・権限・置き場）、依頼は止める
            try:
                output["registered"] = await _register_images(session, job, service, result)
            except (V3Error, RuntimeError) as e:
                await session.rollback()
                raise ApplicationError(f"絵の登録を断られた: {e}", {"retry_after": None}, type="refused",
                                       non_retryable=True) from e
        if job.process in KNOWN_PROCESSES:
            # 答えを読み、要るものを正本に入れる（依頼した人の代わりのAIとして、操作の窓口を通す）
            actor = Actor(kind="ai", id=f"service:{service.id}", on_behalf_of=job.requested_by)
            try:
                output = await handle_known_result(session, job, actor, await _get_authz(), output)
            except BrokenAnswerError as e:
                await session.rollback()
                job = await session.get(Job, job_id)
                job.result = output
                await session.commit()
                raise ApplicationError(str(e), {"retry_after": None}, type="broken_response",
                                       non_retryable=True) from e
            except V3Error as e:
                await session.rollback()
                raise ApplicationError(f"答えを正本に入れるのを断られた: {e}", {"retry_after": None}, type="refused",
                                       non_retryable=True) from e
        job.result = output
        job.status = "done"
        job.failure_kind = job.failure_detail = None
        await session.commit()


@activity.defn
async def set_job_status(job_id: str, status: str, failure_kind: str | None, detail: str | None) -> None:
    async with get_sessionmaker()() as session:
        job = await session.get(Job, job_id)
        job.status = status
        job.failure_kind = failure_kind
        job.failure_detail = detail
        await session.commit()
