"""作業の流れ（WorkUnitWorkflow）の筋道だけを、時間を飛ばせる Temporal（WorkflowEnvironment.start_time_skipping）と
差し替えた活動で確かめる。DB・ComfyUI・LLM は使わない（本物の Temporal を通す試験は tests/integration/test_harness.py）。

差し替えた活動は段の名前ごとに決めた答えを返し、呼ばれた順を残す。待つのは「活動が呼ばれた」知らせ（asyncio.Event）
で、決まった秒数は待たない。判断待ちの知らせ（review_notice）は env.sleep で時間を飛ばして確かめる。
"""

import asyncio
import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from temporalio import activity
from temporalio.client import WorkflowHandle, WorkflowUpdateFailedError
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from v3server.harness.harness_activities import RecordInput, StepInput
from v3server.harness.unit_workflow import Control, LimitChange, Review, UnitInput, WorkUnitWorkflow

QUEUE = "unit-timeskip"
LIMITS = {"max_attempts": 3, "candidates_per_attempt": 2, "budget_cost": 1000, "budget_seconds": 600,
          "error_stop": 3, "same_failure_restart": 2, "eval_repeats": 1, "disagreement_stop": 2,
          "review_notice_seconds": 3600, "resend_limit": 0, "max_fix_rounds": 1}


class Script:
    """段ごとの答え。answers[step] は (呼ばれた回の番号, args) → 答え の関数。"""

    def __init__(self, answers: dict[str, Callable[[int, dict[str, Any]], dict[str, Any]]]):
        self.answers = answers
        self.steps: list[tuple[str, int, dict[str, Any]]] = []
        self.records: list[RecordInput] = []
        self.count: dict[str, int] = {}
        self.changed = asyncio.Event()

    def acts(self) -> list[Any]:
        @activity.defn(name="run_step")
        async def run_step(inp: StepInput) -> dict[str, Any]:
            n = self.count.get(inp.step, 0) + 1
            self.count[inp.step] = n
            self.steps.append((inp.step, inp.attempt, inp.args))
            self.changed.set()
            fn = self.answers.get(inp.step)
            return fn(n, inp.args) if fn else {}

        @activity.defn(name="record_unit")
        async def record_unit(inp: RecordInput) -> dict[str, Any]:
            self.records.append(inp)
            self.changed.set()
            return {"status": inp.patch.get("status")}

        @activity.defn(name="unit_usage")
        async def unit_usage(unit_id: str) -> dict[str, float]:
            return {"cost_used": 0.0, "seconds_used": 0.0}

        return [run_step, record_unit, unit_usage]

    async def until(self, cond: Callable[[], bool], timeout: float = 20) -> None:
        async def loop() -> None:
            while not cond():
                self.changed.clear()
                await self.changed.wait()
        await asyncio.wait_for(loop(), timeout)

    def statuses(self) -> list[str]:
        return [r.patch["status"] for r in self.records if "status" in r.patch]

    def events(self, name: str) -> list[RecordInput]:
        return [r for r in self.records if r.event == name]

    def called(self, step: str) -> list[dict[str, Any]]:
        return [a for s, _, a in self.steps if s == step]


@pytest.fixture(scope="module")
async def env():
    e = await WorkflowEnvironment.start_time_skipping()
    yield e
    await e.shutdown()


async def _start(env: WorkflowEnvironment, script: Script, completion: list[str], **lim: Any
                 ) -> tuple[Worker, WorkflowHandle]:
    worker = Worker(env.client, task_queue=QUEUE, workflows=[WorkUnitWorkflow], activities=script.acts())
    handle = await env.client.start_workflow(
        WorkUnitWorkflow.run, UnitInput("u" + uuid.uuid4().hex, "panel_drawing", {**LIMITS, **lim}, completion),
        id=f"unit-{uuid.uuid4().hex}", task_queue=QUEUE)
    return worker, handle


def _check(passed: int, fixable: list[str] | None = None, failure: str | None = None) -> dict[str, Any]:
    return {"passed": passed, "fixable": fixable or [], "failure": failure}


async def test_落ちた所を直して検査し直し_通れば評価へ進む(env):
    s = Script({"check": lambda n, a: _check(0, ["c1"], "check:文字") if n == 1 else _check(1),
                "evaluate": lambda n, a: {"picked": "c1f", "disagree": False, "failure": None}})
    worker, h = await _start(env, s, ["evaluator_pick"])
    async with worker:
        out = await h.result()
    assert out == {"status": "done", "picked": "c1f"}
    assert [x[0] for x in s.steps] == ["cut_out", "context", "generate", "check", "fix", "check", "evaluate"]
    assert s.called("fix")[0]["candidate_ids"] == ["c1"] and s.called("fix")[0]["round"] == 1
    assert not s.events("fix_fallback")


async def test_直す上限で落ちたままなら_記録してから文脈から作り直し_上限回数で止まる(env):
    s = Script({"check": lambda n, a: _check(0, ["c1"], "check:顔")})
    worker, h = await _start(env, s, ["evaluator_pick"], max_attempts=2)
    async with worker:
        await s.until(lambda: "stopped" in s.statuses())
        fb = s.events("fix_fallback")
        assert len(fb) == 2 and "直す上限（1回）" in fb[0].extra["reason"]
        assert fb[0].extra["decision"].startswith("全部を作り直す")
        # 回ごとに直すのは1回まで（max_fix_rounds）。2回目の回は文脈から
        assert [x[0] for x in s.steps].count("fix") == 2 and [x[0] for x in s.steps].count("context") == 2
        await h.execute_update(WorkUnitWorkflow.control, Control("cancel_unit", "human:a"))
        assert (await h.result())["status"] == "cancelled"
    assert s.called("discard_round")[-1]["reason"] == "作業を取り消した"


async def test_直せない理由で落ちたら直さずに作り直す(env):
    s = Script({"check": lambda n, a: _check(0, [], "check:寸法") if n == 1 else _check(1),
                "evaluate": lambda n, a: {"picked": "c9", "disagree": False, "failure": None}})
    worker, h = await _start(env, s, ["evaluator_pick"])
    async with worker:
        assert (await h.result())["picked"] == "c9"
    assert "fix" not in [x[0] for x in s.steps]
    assert "直せる所（文字・顔）でない理由" in s.events("fix_fallback")[0].extra["reason"]


async def test_質問に答えると答えが次の回の文脈に入り_今の回の候補は却下になる(env):
    s = Script({"check": lambda n, a: _check(1),
                "finalize": lambda n, a: {"candidate_id": a["candidate_id"]}})
    worker, h = await _start(env, s, ["human_approve"])
    async with worker:
        await s.until(lambda: s.statuses().count("awaiting_review") == 1)
        await h.execute_update(WorkUnitWorkflow.review, Review("answer", "human:a", reason="主人公は左利き"))
        await s.until(lambda: s.statuses().count("awaiting_review") == 2)
        await h.execute_update(WorkUnitWorkflow.review, Review("answer", "human:a", reason="舞台は冬"))
        await s.until(lambda: s.statuses().count("awaiting_review") == 3)
        await h.execute_update(WorkUnitWorkflow.review, Review("approve", "human:a", candidate_id="c3"))
        out = await h.result()
    assert out == {"status": "done", "candidate_id": "c3"}
    assert [a["answers"] for a in s.called("context")] == [[], ["主人公は左利き"], ["主人公は左利き", "舞台は冬"]]
    assert [a["reason"] for a in s.called("discard_round")] == ["人が質問に答えた（次の回で答えを入れて作り直す）"] * 2
    assert s.called("finalize")[0]["by"] == "human:a"


async def test_答えの無い答えは断る(env):
    s = Script({"check": lambda n, a: _check(1)})
    worker, h = await _start(env, s, ["human_approve"])
    async with worker:
        await s.until(lambda: "awaiting_review" in s.statuses())
        with pytest.raises(WorkflowUpdateFailedError) as e:
            await h.execute_update(WorkUnitWorkflow.review, Review("answer", "human:a", reason=" "))
        assert "答え（reason）が要る" in str(e.value.cause)
        await h.execute_update(WorkUnitWorkflow.control, Control("cancel_unit", "human:a"))
        assert (await h.result())["status"] == "cancelled"


async def test_判断待ちが長いと決めた間隔ごとに知らせる(env):
    s = Script({"check": lambda n, a: _check(1)})
    worker, h = await _start(env, s, ["human_approve"], review_notice_seconds=3600)
    async with worker:
        await s.until(lambda: "awaiting_review" in s.statuses())
        await env.sleep(timedelta(hours=2, minutes=1))
        await s.until(lambda: len(s.events("review_notice")) >= 2)
        assert [r.extra["waited_notices"] for r in s.events("review_notice")][:2] == [1, 2]
        await h.execute_update(WorkUnitWorkflow.control, Control("cancel_unit", "human:a"))
        assert (await h.result())["status"] == "cancelled"


async def test_評価が割れ続けると止まり_上限を上げると続く(env):
    s = Script({"check": lambda n, a: _check(2),
                "evaluate": lambda n, a: ({"picked": None, "disagree": True, "failure": "evaluate:割れた"} if n <= 2
                                          else {"picked": "c5", "disagree": False, "failure": None})})
    worker, h = await _start(env, s, ["evaluator_pick"], disagreement_stop=2)
    async with worker:
        await s.until(lambda: "stopped" in s.statuses())
        st = await h.query(WorkUnitWorkflow.state)
        assert st["s"]["disagreements"] == 2 and st["s"]["failures"] == ["evaluate:割れた"] * 2
        # 割れた数の上限を上げると、止まる理由が消えるのでそのまま続く（再開の操作は要らない）
        await h.execute_update(WorkUnitWorkflow.set_limits, LimitChange("human:a", {"disagreement_stop": 5}))
        assert (await h.result())["picked"] == "c5"
    assert s.events("limits")[0].extra == {"by": "human:a"}


async def test_エラーが続くと止まり_再開すると続く(env):
    def generate(n, a):
        if n <= 2:
            raise ApplicationError("偽の失敗", type="generation_failed", non_retryable=True)
        return {}
    s = Script({"generate": generate, "check": lambda n, a: _check(1),
                "evaluate": lambda n, a: {"picked": "c1", "disagree": False, "failure": None}})
    worker, h = await _start(env, s, ["evaluator_pick"], error_stop=2)
    async with worker:
        await s.until(lambda: "stopped" in s.statuses())
        assert [r.extra["type"] for r in s.events("error")] == ["generation_failed"] * 2
        stopped = next(r.patch["stop_reason"] for r in s.records if r.patch.get("status") == "stopped")
        assert "エラーが2回続いた" in stopped
        await h.execute_update(WorkUnitWorkflow.control, Control("resume", "human:a"))
        assert (await h.result())["picked"] == "c1"


async def test_段の切れ目で止めると今の段を終えてから止まり_再開で続く(env):
    gate, started = asyncio.Event(), asyncio.Event()
    s = Script({"check": lambda n, a: _check(1),
                "evaluate": lambda n, a: {"picked": "c1", "disagree": False, "failure": None}})
    acts = s.acts()

    @activity.defn(name="run_step")
    async def run_step(inp: StepInput) -> dict[str, Any]:
        if inp.step == "generate":
            started.set()
            await gate.wait()
        return await acts[0](inp)

    worker = Worker(env.client, task_queue=QUEUE, workflows=[WorkUnitWorkflow], activities=[run_step, *acts[1:]])
    h = await env.client.start_workflow(
        WorkUnitWorkflow.run, UnitInput("u" + uuid.uuid4().hex, "panel_drawing", LIMITS, ["evaluator_pick"]),
        id=f"unit-{uuid.uuid4().hex}", task_queue=QUEUE)
    async with worker:
        await asyncio.wait_for(started.wait(), 20)  # 生成の段が動いている間に止める
        await h.execute_update(WorkUnitWorkflow.control, Control("pause", "human:a", "boundary"))
        gate.set()
        await s.until(lambda: "paused" in s.statuses())
        # 生成は終えてから止まる（検査へは進まない）
        assert [x[0] for x in s.steps][-1] == "generate"
        await h.execute_update(WorkUnitWorkflow.control, Control("resume", "human:a"))
        assert (await h.result())["picked"] == "c1"
    assert [x[0] for x in s.steps][-2:] == ["check", "evaluate"]
