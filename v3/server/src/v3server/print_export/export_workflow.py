"""書き出しの流れ（Temporal）。書き出しの依頼（ExportRun）を1件ずつ、書き出しの待ち行列の作業者が行う。

- 待ち行列は v3-export（生成の待ち行列とは分ける。書き出しが生成の順番を待たないように）
- 足りない値で止めたとき（ExportRefused・RenderRefused など値の問題）は送り直さず failed にし、理由を detail に書く
"""

from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

EXPORT_QUEUE = "v3-export"


@activity.defn(name="run_export")
async def run_export_activity(run_id: str) -> None:
    from v3server.canonical_tables.material_and_setting_tables import ExportRun
    from v3server.database_engine import get_sessionmaker
    from v3server.print_export.export_runner import run_export

    async with get_sessionmaker()() as session:
        run = await session.get(ExportRun, run_id)
        run.status, run.detail = "running", None
        await session.commit()
        try:
            outputs = await run_export(session, run)
        except Exception as e:  # 理由を記録してから、送り直さない失敗として返す
            await session.rollback()
            run = await session.get(ExportRun, run_id)
            run.status, run.detail = "failed", f"{type(e).__name__}: {e}"
            await session.commit()
            raise ApplicationError(run.detail, non_retryable=True) from e
        run.status, run.outputs = "done", outputs
        await session.commit()


@workflow.defn(name="ExportRunWorkflow")
class ExportRunWorkflow:
    @workflow.run
    async def run(self, run_id: str) -> None:
        await workflow.execute_activity(
            "run_export", run_id, task_queue=EXPORT_QUEUE,
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
