"""Temporal の活動。正本（PostgreSQL）を読み書きするのはここだけ。"""

import time
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from temporalio import activity
from temporalio.exceptions import ApplicationError

from ..db import get_sessionmaker
from ..destinations import is_allowed
from ..models import CallLog, Job, Service, ServiceProcess
from . import adapters

# ここに載った種類は、活動の中では送り直さない（workflows.py が種類ごとに扱う）
NON_RETRYABLE = ["rate_limited", "refused", "broken_response", "budget", "destination_not_allowed"]


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
        try:
            result = await adapters.ADAPTERS[service.adapter](service, sp, job.request)
        except adapters.AdapterError as e:
            await stop(e.kind, e.detail, e.retry_after)
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
        job.result = result.output
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
