"""ハーネスの作業者（`uv run python -m v3server.harness.harness_worker_main`）。

工程の進行役と作業の流れ（キュー v3-harness）と、上流の変化を見る所（upstream_watch）を1つのプロセスで動かす。
生成・検出器・LLM の送信は今の作業者（queue_worker_main）が受ける。ハーネスは順番待ちに頼むだけ。
"""

import asyncio
import logging
from datetime import timedelta

from temporalio.client import Client
from temporalio.worker import Worker

from v3server.harness import queue_calls, upstream_watch
from v3server.harness.harness_activities import ACTIVITIES
from v3server.harness.stage_workflow import HARNESS_QUEUE, StageWorkflow
from v3server.harness.unit_workflow import WorkUnitWorkflow
from v3server.server_settings import get_settings


class HarnessWorker:
    def __init__(self, client: Client, watch: bool = True):
        self.client = client
        self.watch = watch
        self.worker: Worker | None = None
        self.tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        queue_calls.configure(self.client)
        self.worker = Worker(self.client, task_queue=HARNESS_QUEUE, workflows=[StageWorkflow, WorkUnitWorkflow],
                             activities=ACTIVITIES,
                             # 取り消しは生存の知らせの返事で届く。既定の間引き（生存の時間切れの8割）では人の
                             # 「今すぐ止める」が十数秒遅れるので、1秒に1回は送る
                             max_heartbeat_throttle_interval=timedelta(seconds=1),
                             default_heartbeat_throttle_interval=timedelta(seconds=1))
        self.tasks.append(asyncio.create_task(self.worker.run()))
        if self.watch:
            self.tasks.append(asyncio.create_task(upstream_watch.run_forever(self.client)))

    async def shutdown(self) -> None:
        if self.worker is not None:
            await self.worker.shutdown()
        for t in self.tasks:
            t.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    client = await Client.connect(get_settings().temporal_address)
    hw = HarnessWorker(client)
    await hw.start()
    try:
        await asyncio.Event().wait()
    finally:
        await hw.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
