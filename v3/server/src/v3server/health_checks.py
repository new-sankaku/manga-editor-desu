"""中身まで見るヘルスチェック。口（GET /health/ready）と、コンテナのヘルスチェック（python -m v3server.health_checks）で使う。

- api: DB・OpenFGA・Temporal・絵の置き場に届くか
- worker: 上に加えて、制御と書き出しの待ち行列を作業者が取りに来ているか（Temporal に問い合わせる）
"""

import asyncio
import sys
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import text
from temporalio.api.enums.v1 import TaskQueueType
from temporalio.api.taskqueue.v1 import TaskQueue
from temporalio.api.workflowservice.v1 import DescribeTaskQueueRequest
from temporalio.client import Client

from v3server.database_engine import get_sessionmaker
from v3server.generation_queue.queue_names_and_priority import CONTROL_QUEUE
from v3server.image_file_storage import image_store
from v3server.print_export.export_workflow import EXPORT_QUEUE
from v3server.server_settings import get_settings


async def _database() -> None:
    async with get_sessionmaker()() as session:
        await session.execute(text("select 1"))


async def _openfga() -> None:
    async with httpx.AsyncClient(base_url=get_settings().openfga_url, timeout=5) as c:
        (await c.get("/healthz")).raise_for_status()


async def _temporal(client: Client) -> None:
    await client.service_client.check_health(timeout=timedelta(seconds=5))


async def _image_store() -> None:
    await asyncio.to_thread(image_store().check)


async def _pollers(client: Client) -> None:
    for queue in (CONTROL_QUEUE, EXPORT_QUEUE):
        r = await client.workflow_service.describe_task_queue(DescribeTaskQueueRequest(
            namespace=client.namespace, task_queue=TaskQueue(name=queue),
            task_queue_type=TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW))
        if not r.pollers:
            raise RuntimeError(f"待ち行列 {queue} を取りに来る作業者がいない")


async def readiness(client: Client, include_workers: bool = False) -> dict[str, Any]:
    checks = {"database": _database(), "openfga": _openfga(), "temporal": _temporal(client),
              "image_store": _image_store()}
    if include_workers:
        checks["workers"] = _pollers(client)
    results = await asyncio.gather(*checks.values(), return_exceptions=True)
    detail = {name: "ok" if r is None else f"{type(r).__name__}: {r}" for name, r in zip(checks, results, strict=False)}
    return {"ok": all(v == "ok" for v in detail.values()), "checks": detail}


async def _main(kind: str) -> int:
    client = await Client.connect(get_settings().temporal_address)
    result = await readiness(client, include_workers=kind == "worker")
    print(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("api", "worker"):
        sys.exit("使い方: python -m v3server.health_checks api|worker")
    sys.exit(asyncio.run(_main(sys.argv[1])))
