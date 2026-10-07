"""1件の依頼の流れ（V3細部の決めごと 4.2・4.5）。

- 依頼の流れは制御の待ち行列（CONTROL_QUEUE）で動き、つなぎ先への送信は、つなぎ先ごとの待ち行列で動く
- 「1件ずつ」「同時にN件まで」は、つなぎ先ごとの待ち行列の作業者の同時実行数で決まる（queue/worker.py）
- 休ませたつなぎ先は作業者を止めるので、頼んだものは待ち行列に残り、戻すと順に送られる
- 失敗したとき、別のつなぎ先へは回さない（方針7）
"""

import asyncio
from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import Priority, RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError, CancelledError

with workflow.unsafe.imports_passed_through():
    from .activities import NON_RETRYABLE

CONTROL_QUEUE = "v3-control"

# 人が画面で頼んだものを先にする（V3細部の決めごと 4.4）。Temporal は数が小さいほど先
PRIORITY_KEY = {"human": 1, "ai": 3}

# 制限に当たったとき、提供元が待ち時間を返さなかった場合に待つ時間
RATE_LIMIT_WAIT = timedelta(seconds=30)


def service_queue(service_id: str) -> str:
    return f"v3-service-{service_id}"


@dataclass
class JobInput:
    job_id: str
    service_id: str
    requested_via: str
    resend_limit: int


@workflow.defn
class GenerationJob:
    def __init__(self) -> None:
        self._resumed = False

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
                    await workflow.execute_activity(
                        "call_service",
                        inp.job_id,
                        task_queue=service_queue(inp.service_id),
                        # 待ち行列に入ってから終わるまで。休ませている間は待ち続ける
                        schedule_to_start_timeout=None,
                        start_to_close_timeout=timedelta(minutes=30),
                        retry_policy=RetryPolicy(
                            initial_interval=timedelta(seconds=5),
                            backoff_coefficient=2,
                            maximum_attempts=inp.resend_limit + 1,
                            non_retryable_error_types=NON_RETRYABLE,
                        ),
                        priority=Priority(priority_key=PRIORITY_KEY[inp.requested_via]),
                    )
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
