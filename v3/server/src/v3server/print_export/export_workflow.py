"""書き出しの流れ（Temporal）。書き出しの依頼（ExportRun）を1件ずつ、書き出しの待ち行列の作業者が行う。

- 待ち行列は v3-export（生成の待ち行列とは分ける。書き出しが生成の順番を待たないように）
- 足りない値で止めたとき（ExportRefused・RenderRefused など値の問題）は送り直さず failed にし、理由を detail に書く
- 作業者が途中で落ちたとき：書き出しの間は生存の知らせ（heartbeat）を送り続け、途絶えたら Temporal が別の作業者で
  初めからやり直す（同じフォルダに同じ名前で書き直す）。前は送り直しが1回きりで生存の知らせも無く、作業者を止めると
  ExportRun が running のまま残った（2026-10-08 保存と再起動の確かめで見つけた。V3サーバーの土台「保存と再起動の確かめ」）
- やり直しても終わるのは1回だけ：もう done の依頼は何もしないで返す。やり直しの回数を使い切ったら failed にして理由を残す
"""

import asyncio
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

EXPORT_QUEUE = "v3-export"
# 生存の知らせの間と、途絶えたとみなすまでの時間。描く・書くは別のスレッドで行うので（export_runner.off_loop）、
# 書き出しの最中もイベントループは空いていて、知らせは止まらない
HEARTBEAT_SECONDS = 2
HEARTBEAT_TIMEOUT = timedelta(seconds=20)
# 作業者が落ちたときにやり直す回数（初めの1回を含む）
MAX_ATTEMPTS = 3


async def _keep_alive() -> None:
    while True:
        activity.heartbeat()
        await asyncio.sleep(HEARTBEAT_SECONDS)


@activity.defn(name="run_export")
async def run_export_activity(run_id: str) -> None:
    from v3server.canonical_tables.material_and_setting_tables import ExportRun
    from v3server.database_engine import get_sessionmaker
    from v3server.print_export.export_runner import run_export

    beat = asyncio.create_task(_keep_alive())
    try:
        async with get_sessionmaker()() as session:
            run = await session.get(ExportRun, run_id)
            if run.status == "done":
                # 前の回で書き終えて、終わりの知らせだけが届かなかった。2回は書かない
                return
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
    finally:
        beat.cancel()


@activity.defn(name="mark_export_failed")
async def mark_export_failed_activity(run_id: str, reason: str) -> None:
    """やり直しを使い切ったとき（作業者が続けて落ちた・時間切れ）に、依頼を failed にして理由を残す。"""
    from v3server.canonical_tables.material_and_setting_tables import ExportRun
    from v3server.database_engine import get_sessionmaker

    async with get_sessionmaker()() as session:
        run = await session.get(ExportRun, run_id)
        if run.status in ("done", "failed"):
            return
        run.status, run.detail = "failed", reason
        await session.commit()


@workflow.defn(name="ExportRunWorkflow")
class ExportRunWorkflow:
    @workflow.run
    async def run(self, run_id: str) -> None:
        try:
            await workflow.execute_activity(
                "run_export", run_id, task_queue=EXPORT_QUEUE,
                start_to_close_timeout=timedelta(minutes=30),
                heartbeat_timeout=HEARTBEAT_TIMEOUT,
                retry_policy=RetryPolicy(maximum_attempts=MAX_ATTEMPTS),
            )
        except ActivityError as e:
            cause = e.cause
            if isinstance(cause, ApplicationError) and cause.non_retryable:
                # 値の問題。依頼はもう failed で、理由も書いてある
                raise
            await workflow.execute_activity(
                "mark_export_failed", args=[run_id, f"書き出しを {MAX_ATTEMPTS} 回やり直しても終わらなかった（{cause or e}）"],
                task_queue=EXPORT_QUEUE, start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(maximum_attempts=0),
            )
            raise


# 書き出しの待ち行列の作業者が受ける作業（queue_worker_main.WorkerSet）
EXPORT_ACTIVITIES = [run_export_activity, mark_export_failed_activity]
