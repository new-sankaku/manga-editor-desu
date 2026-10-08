"""1件の依頼の流れ（V3細部の決めごと 4.2・4.5）。

- 依頼の流れは制御の待ち行列（CONTROL_QUEUE）で動き、つなぎ先への送信は、つなぎ先ごとの待ち行列で動く
- 「1件ずつ」「同時にN件まで」は、つなぎ先ごとの待ち行列の作業者の同時実行数で決まる（generation_queue/queue_worker_main.py）
- 休ませたつなぎ先は作業者を止めるので、頼んだものは待ち行列に残り、戻すと順に送られる
- 失敗したとき、別のつなぎ先へは回さない（方針7）
- 依頼を受ける口（job_start_and_control.enqueue）は、流れを始めるのと一緒に until_queued を送り、送信をつなぎ先の
  待ち行列に入れ終えてから返す。同じ扱いの依頼を頼んだ順に送るため（V3細部の決めごと 4.4）。流れを始めただけで返すと、
  続けて頼んだ依頼の送信が、制御の作業者と Temporal の中で前後して待ち行列に入る（2026-10-08 実測。V3サーバーの土台 7章）
"""

import asyncio
from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError, CancelledError

with workflow.unsafe.imports_passed_through():
    from v3server.generation_queue.queue_names_and_priority import (
        CONTROL_QUEUE,
        RATE_LIMIT_WAIT,
        job_priority,
        service_queue,
    )
    from v3server.generation_queue.service_call_activity import NON_RETRYABLE

@dataclass
class JobInput:
    job_id: str
    work_id: str
    service_id: str
    requested_via: str
    resend_limit: int


@workflow.defn
class GenerationJob:
    def __init__(self) -> None:
        self._resumed = False
        self._queued = False

    @workflow.update
    async def until_queued(self) -> None:
        """送信をつなぎ先の待ち行列に入れるまで待つ。"""
        await workflow.wait_condition(lambda: self._queued)

    @workflow.signal
    def resume(self) -> None:
        """予算の上限で止まったものを、人が上限を上げたあとに続ける。"""
        self._resumed = True

    async def _status(self, status: str, kind: str | None = None, detail: str | None = None) -> None:
        await workflow.execute_activity(
            "set_job_status",
            args=[self.job_id, status, kind, detail],
            task_queue=CONTROL_QUEUE,
            start_to_close_timeout=timedelta(seconds=30),
        )

    @workflow.run
    async def run(self, inp: JobInput) -> str:
        self.job_id = inp.job_id
        try:
            while True:
                try:
                    sending = workflow.start_activity(
                        "call_service",
                        inp.job_id,
                        task_queue=service_queue(inp.service_id),
                        # 待ち行列に入ってから終わるまで。休ませている間は待ち続ける
                        schedule_to_start_timeout=None,
                        start_to_close_timeout=timedelta(minutes=30),
                        # 活動が生存を知らせる間隔の数倍。取り消しは、この知らせの返事で活動に届く
                        heartbeat_timeout=timedelta(seconds=30),
                        retry_policy=RetryPolicy(
                            initial_interval=timedelta(seconds=5),
                            backoff_coefficient=2,
                            maximum_attempts=inp.resend_limit + 1,
                            non_retryable_error_types=NON_RETRYABLE,
                        ),
                        priority=job_priority(inp.requested_via, inp.work_id),
                    )
                    # 送信を待ち行列に入れる指示と until_queued の返事は、同じワークフロータスクの結果として一緒に Temporal に渡る
                    self._queued = True
                    await sending
                    return "done"
                except ActivityError as e:
                    cause = e.cause
                    if isinstance(cause, CancelledError):
                        raise asyncio.CancelledError() from e
                    kind = cause.type if isinstance(cause, ApplicationError) else None
                    detail = cause.message if isinstance(cause, ApplicationError) else str(e)
                    if kind == "rate_limited":
                        retry_after = (cause.details[0] or {}).get("retry_after") if cause.details else None
                        await self._status("waiting_limit", kind, detail)
                        await workflow.sleep(timedelta(seconds=retry_after) if retry_after else RATE_LIMIT_WAIT)
                        continue
                    if kind == "budget":
                        await self._status("waiting_budget", kind, detail)
                        self._resumed = False
                        await workflow.wait_condition(lambda: self._resumed)
                        continue
                    await self._status("stopped", kind or "transport", detail)
                    return "stopped"
        except asyncio.CancelledError:
            # 人が取り消した、またはAIのロックを人が取り返した
            await self._status("cancelled")
            raise
