"""P60 の作業者。別のプロセスで動かし、試験の途中で落として起動し直す。
実行: v3/server/.venv/bin/python worker.py"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from temporalio.client import Client  # noqa: E402
from temporalio.worker import UnsandboxedWorkflowRunner, Worker  # noqa: E402

import harness_activities  # noqa: E402
from harness_config import TASK_QUEUE, TEMPORAL_ADDR  # noqa: E402
from harness_workflows import StageWorkflow, WorkUnitWorkflow  # noqa: E402


async def main() -> None:
    client = await Client.connect(TEMPORAL_ADDR)
    worker = Worker(client, task_queue=TASK_QUEUE, workflows=[WorkUnitWorkflow, StageWorkflow],
                    activities=harness_activities.ALL, workflow_runner=UnsandboxedWorkflowRunner(),
                    max_concurrent_activities=8)
    print("worker ready", flush=True)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
