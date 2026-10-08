"""保存と再起動の確かめ（v3/web/test/persistence_e2e.mjs）の作業者。試験の外では使わない。

今の作業者（queue_worker_main の WorkerSet）とハーネスの作業者（HarnessWorker）を、本物と同じ Temporal・PostgreSQL に
つないで1つのプロセスで動かす。違うのは LLM と検出器の送り手だけで、どちらも偽物（tests/integration/harness_fakes.py の
fake_llm・fake_detector）に差し替える。ComfyUI は本物の送り手（comfyui）のまま、偽の ComfyUI（fake_comfy_main.py）へ送る。

  uv run python tests/persistence/fake_workers_main.py

設定は本物と同じ環境変数（V3_DATABASE_URL など）で受ける。
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "integration"))

from harness_fakes import Script, fake_detector, fake_llm  # noqa: E402
from temporalio.client import Client  # noqa: E402

from v3server.generation_queue.queue_worker_main import WorkerSet  # noqa: E402
from v3server.harness.harness_worker_main import HarnessWorker  # noqa: E402
from v3server.image_file_storage import image_store  # noqa: E402
from v3server.server_settings import get_settings  # noqa: E402
from v3server.service_senders.sender_by_adapter_name import ADAPTERS  # noqa: E402


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger(__name__).warning("偽の LLM・検出器で動かす作業者（保存と再起動の確かめ用）")
    image_store().check()
    script = Script()
    ADAPTERS["litellm"] = fake_llm(script)
    ADAPTERS["detector"] = fake_detector(script)
    client = await Client.connect(get_settings().temporal_address)
    workers = WorkerSet(client)
    harness = HarnessWorker(client)
    await workers.start()
    await harness.start()
    print("WORKERS READY", flush=True)
    try:
        await workers.keep_reloading()
    finally:
        await harness.shutdown()
        await workers.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
