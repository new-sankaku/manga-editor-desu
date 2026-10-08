"""Temporal の作業者をまとめて動かす。`uv run python -m v3server.generation_queue.queue_worker_main`

- 制御の待ち行列: 依頼の流れと、状態の書き込み
- 書き出しの待ち行列（v3-export）: 書き出し（PNG・PDF・PSD）。print_export/export_workflow.py
- つなぎ先ごとの待ち行列: 送信。同時実行数は「1件ずつ」なら1、「同時にN件まで」ならN
- つなぎ先の表を数秒ごとに読み直し、休ませた・数を変えた先の作業者を止めて作り直す
"""

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import select
from temporalio.client import Client
from temporalio.worker import Worker

from v3server.canonical_tables.service_and_job_tables import Service
from v3server.database_engine import get_sessionmaker
from v3server.generation_queue.generation_workflow import GenerationJob
from v3server.generation_queue.queue_names_and_priority import (
    CONTROL_QUEUE,
    service_queue,
)
from v3server.generation_queue.service_call_activity import call_service, set_job_status
from v3server.print_export.export_workflow import EXPORT_QUEUE, ExportRunWorkflow, run_export_activity
from v3server.server_settings import get_settings

log = logging.getLogger(__name__)

RELOAD_SECONDS = 3


def concurrency(service: Service) -> int:
    return 1 if service.send_mode == "serial" else service.max_concurrency


class WorkerSet:
    def __init__(self, client: Client):
        self.client = client
        self.control: Worker | None = None
        self._control_task: asyncio.Task | None = None
        self.export: Worker | None = None
        self._export_task: asyncio.Task | None = None
        # service_id -> (同時実行数, 作業者, 動かしている task)
        self.services: dict[str, tuple[int, Worker, asyncio.Task]] = {}

    async def start(self) -> None:
        self.control = Worker(
            self.client,
            task_queue=CONTROL_QUEUE,
            workflows=[GenerationJob],
            activities=[set_job_status],
        )
        self._control_task = asyncio.create_task(self.control.run())
        self.export = Worker(
            self.client,
            task_queue=EXPORT_QUEUE,
            workflows=[ExportRunWorkflow],
            activities=[run_export_activity],
        )
        self._export_task = asyncio.create_task(self.export.run())
        await self.reload()

    async def reload(self) -> None:
        async with get_sessionmaker()() as session:
            services = (await session.execute(select(Service))).scalars().all()
        desired = {s.id: concurrency(s) for s in services if not s.paused}

        for sid in list(self.services):
            if desired.get(sid) != self.services[sid][0]:
                await self._stop(sid)
        for sid, n in desired.items():
            if sid not in self.services:
                worker = Worker(
                    self.client,
                    task_queue=service_queue(sid),
                    activities=[call_service],
                    max_concurrent_activities=n,
                    # 取り消しは生存の知らせの返事で届く。既定の間引き（時間切れ30秒の8割=24秒）だと、人が止めても
                    # ComfyUI が描き終えるまで届かないことがある（ハーネスの試験で見つけた）。1秒に1回は送る
                    max_heartbeat_throttle_interval=timedelta(seconds=1),
                    default_heartbeat_throttle_interval=timedelta(seconds=1),
                )
                self.services[sid] = (n, worker, asyncio.create_task(worker.run()))
                log.info("つなぎ先 %s の作業者を動かした（同時に %d 件）", sid, n)

    async def _stop(self, sid: str) -> None:
        _, worker, task = self.services.pop(sid)
        await worker.shutdown()
        await task
        log.info("つなぎ先 %s の作業者を止めた", sid)

    async def shutdown(self) -> None:
        for sid in list(self.services):
            await self._stop(sid)
        if self.control:
            await self.control.shutdown()
            await self._control_task
        if self.export:
            await self.export.shutdown()
            await self._export_task

    async def run_forever(self) -> None:
        await self.start()
        try:
            while True:
                await asyncio.sleep(RELOAD_SECONDS)
                await self.reload()
        finally:
            await self.shutdown()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    client = await Client.connect(get_settings().temporal_address)
    await WorkerSet(client).run_forever()


if __name__ == "__main__":
    asyncio.run(main())
