"""段の中の順番待ちの数え方（queue_calls.wait_jobs と WaitClock）を、依頼の状態を差し替えて確かめる。

p60 で、時間の上限に順番待ちを数えると、混んだときに1台の ComfyUI を待つだけで作業が止まった。今は、依頼がどれも
動いていない間を待ちとして別に数え（時間の上限には入れない）、待ちの上限を超えたら依頼を取り消して wait_limit で止める。
"""

import asyncio
from types import SimpleNamespace

import pytest
from temporalio.exceptions import ApplicationError

from v3server.harness import queue_calls as q


class FakeSession:
    def __init__(self, timeline):
        self.timeline = timeline

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, model, jid):
        return SimpleNamespace(id=jid, status=self.timeline[0])


@pytest.fixture
def fake_queue(monkeypatch):
    """依頼の状態を、見るたびに timeline の先頭から1つずつ進める。"""
    timeline: list[str] = []
    cancelled: list[list[str]] = []

    def sessionmaker():
        def make():
            s = FakeSession(timeline)
            if len(timeline) > 1:
                timeline.pop(0)
            return s
        return make

    async def cancel(job_ids):
        cancelled.append(job_ids)

    monkeypatch.setattr(q, "get_sessionmaker", sessionmaker)
    monkeypatch.setattr(q, "_cancel_and_wait", cancel)
    monkeypatch.setattr(q.activity, "heartbeat", lambda *a: None)
    monkeypatch.setattr(q, "POLL_SECONDS", 0.01)
    return timeline, cancelled


async def test_動いていない間だけを待ちとして数える(fake_queue):
    timeline, _ = fake_queue
    timeline += ["queued"] * 5 + ["running"] * 5 + ["done"]
    clock = q.WaitClock(limit=None)
    q.WAIT_CLOCK.set(clock)
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    (job,) = await q.wait_jobs(None, ["j1"])
    total = loop.time() - t0
    assert job.status == "done"
    # 順番待ちを見た回の前の間は数え、動いているのを見た回の前の間（5回）は数えない。
    # 最初に見る前に1つ進むので、順番待ちを見るのは4回で、数える間は3回。
    # 見回りの間は 0.01 秒より短くならないので、下限だけで比べる（混んだ機械で長くなっても外れない）
    assert clock.waited >= 0.03 and total - clock.waited >= 0.05


async def test_待ちの上限を超えたら依頼を取り消してwait_limitで止める(fake_queue):
    timeline, cancelled = fake_queue
    timeline += ["queued"] * 50
    q.WAIT_CLOCK.set(q.WaitClock(limit=0.03))
    with pytest.raises(ApplicationError) as e:
        await q.wait_jobs(None, ["j1", "j2"])
    assert e.value.type == "wait_limit" and e.value.non_retryable
    assert "待ちの上限" in e.value.message
    assert cancelled == [["j1", "j2"]]


async def test_段の外では待ちを数えない(fake_queue):
    timeline, _ = fake_queue
    timeline += ["queued"] * 3 + ["done"]
    q.WAIT_CLOCK.set(None)
    (job,) = await q.wait_jobs(None, ["j1"])
    assert job.status == "done"
