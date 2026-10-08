"""1件の依頼の流れ（generation_workflow.GenerationJob）の決まりを、時間を飛ばせる Temporal の試験用サーバーで確かめる。

活動（call_service・set_job_status）は偽物。本物の活動は test_service_call_activity.py（integration）で直接呼んで確かめる。
送り直しの間隔（5秒・10秒）や制限の待ちは、試験用サーバーが時間を飛ばすので待たない。
本物の Temporal と作業者で通す試験は tests/integration/test_queue.py の test_失敗の種類ごとの扱い（full の組）。
試験用サーバーは temporalio が初回に取ってくる（ネットにつながっていること）。
"""

import asyncio
import uuid
from datetime import timedelta

import pytest
from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from v3server.generation_queue.generation_workflow import GenerationJob, JobInput
from v3server.generation_queue.queue_names_and_priority import CONTROL_QUEUE, RATE_LIMIT_WAIT, service_queue
from v3server.generation_queue.service_call_activity import NON_RETRYABLE

SERVICE = "svc-ts"


@pytest.fixture(scope="module")
async def env():
    e = await WorkflowEnvironment.start_time_skipping()
    yield e
    await e.shutdown()


class FakeActivities:
    """script の順に call_service が振る舞う。"ok" で終わる。それ以外はその種類の失敗（本物と同じ送り直してよいかの印）。"""

    def __init__(self, script: list[str], retry_after: float | None = 1):
        self.script, self.retry_after = script, retry_after
        self.calls = 0
        self.statuses: list[tuple[str, str | None]] = []
        self.started = asyncio.Event()

    @activity.defn(name="call_service")
    async def call_service(self, job_id: str) -> None:
        self.calls += 1
        self.started.set()
        step = self.script[self.calls - 1] if self.calls - 1 < len(self.script) else "ok"
        if step == "hang":
            while True:
                activity.heartbeat()
                await asyncio.sleep(0.05)
        if step != "ok":
            raise ApplicationError(f"試験: {step}", {"retry_after": self.retry_after if step == "rate_limited" else None},
                                   type=step, non_retryable=step in NON_RETRYABLE)

    @activity.defn(name="set_job_status")
    async def set_job_status(self, job_id: str, status: str, failure_kind: str | None, detail: str | None) -> None:
        self.statuses.append((status, failure_kind))


async def run(env, fake: FakeActivities, resend_limit: int, during=None):
    """流れを始め、until_queued が返るのを確かめ、終わるまで待つ。during(handle) を途中で呼ぶ。"""
    job_id = uuid.uuid4().hex
    async with (Worker(env.client, task_queue=CONTROL_QUEUE, workflows=[GenerationJob],
                       activities=[fake.set_job_status]),
                Worker(env.client, task_queue=service_queue(SERVICE), activities=[fake.call_service])):
        handle = await env.client.start_workflow(
            GenerationJob.run, JobInput(job_id=job_id, work_id="w", service_id=SERVICE, requested_via="human",
                                        resend_limit=resend_limit),
            id=f"job-{job_id}", task_queue=CONTROL_QUEUE)
        await handle.execute_update(GenerationJob.until_queued)
        if during:
            await during(handle)
        return await handle.result()


async def test_断られたら送り直さない(env):
    fake = FakeActivities(["refused"])
    assert await run(env, fake, resend_limit=2) == "stopped"
    assert fake.calls == 1
    assert fake.statuses == [("stopped", "refused")]


async def test_通信の失敗は送り直しの回数まで送り直す(env):
    fake = FakeActivities(["transport", "transport", "ok"])
    assert await run(env, fake, resend_limit=2) == "done"
    assert fake.calls == 3
    assert fake.statuses == []


async def test_送り直しの回数を超えたら止める(env):
    fake = FakeActivities(["transport"] * 5)
    assert await run(env, fake, resend_limit=2) == "stopped"
    assert fake.calls == 3
    assert fake.statuses == [("stopped", "transport")]


async def test_制限に当たったら待って同じ先に送り直し_回数に数えない(env):
    fake = FakeActivities(["rate_limited"] * 3 + ["ok"])
    t0 = await env.get_current_time()
    assert await run(env, fake, resend_limit=0) == "done"
    assert fake.calls == 4
    assert fake.statuses == [("waiting_limit", "rate_limited")] * 3
    # 提供元が返した待ち時間（1秒）だけ待つ
    assert await env.get_current_time() - t0 >= timedelta(seconds=3)


async def test_制限の待ち時間が無ければ決めた長さを待つ(env):
    fake = FakeActivities(["rate_limited"], retry_after=None)
    t0 = await env.get_current_time()
    assert await run(env, fake, resend_limit=0) == "done"
    assert await env.get_current_time() - t0 >= RATE_LIMIT_WAIT


async def test_予算の上限では人が続けるまで待つ(env):
    fake = FakeActivities(["budget"])

    async def resume(handle):
        while ("waiting_budget", "budget") not in fake.statuses:
            await asyncio.sleep(0.05)
        assert fake.calls == 1
        await handle.signal(GenerationJob.resume)

    assert await run(env, fake, resend_limit=0, during=resume) == "done"
    assert fake.calls == 2


async def test_取り消すと取り消しの状態にする(env):
    fake = FakeActivities(["hang"])

    async def cancel(handle):
        await fake.started.wait()
        await handle.cancel()

    with pytest.raises(WorkflowFailureError):
        await run(env, fake, resend_limit=0, during=cancel)
    assert fake.statuses == [("cancelled", None)]
