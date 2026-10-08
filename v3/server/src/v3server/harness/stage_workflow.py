"""工程の進行役（親ワークフロー）。1話の1工程の作業を切り出し、同時に回す数を守って子の流れ（作業）を回し、
工程の検査をして、人の承認で次の工程へ進む（continue-as-new で同じ流れの id のまま次の工程になる）。

- 流れの id は harness-episode-{話の id}。1話に工程の進行役は1つだけ動く
- 人の操作（Update。検証つき）：control（pause・resume・cancel）・approve（工程の承認）・rerun（古い作業の作り直し）
- 一時停止・取り消しは子へ知らせる（parent_control）。Python の外の流れへの手渡しでは Update を送れないため Signal
- 上流が変わった作業は、上流を見る所（upstream_watch.py）が古い印を付けて子に知らせる。作り直しは人が rerun で頼む
"""

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError
from temporalio.workflow import ParentClosePolicy

with workflow.unsafe.imports_passed_through():
    from v3server.harness.harness_activities import (
        RecordInput,
        advance_stage,
        prepare_stage,
        record_stage,
        rerun_units,
        stage_check,
    )
    from v3server.harness.unit_workflow import Control, UnitInput, WorkUnitWorkflow

HARNESS_QUEUE = "v3-harness"
SHORT = timedelta(seconds=60)
CHECK_TIMEOUT = timedelta(minutes=30)


@dataclass
class StageInput:
    stage_run_id: str
    # StageLimits の形（unit・max_parallel_units・completion）
    limits: dict[str, Any]


@dataclass
class StageControl:
    action: str
    by: str


@dataclass
class Rerun:
    by: str
    unit_ids: list[str] = field(default_factory=list)


def stage_workflow_id(episode_id: str) -> str:
    return f"harness-episode-{episode_id}"


@workflow.defn
class StageWorkflow:
    def __init__(self) -> None:
        self.run_id = ""
        self.limits: dict[str, Any] = {}
        self.kind: str | None = None
        self.status = "queued"
        self.pending: list[str] = []
        self.running: dict[str, Any] = {}
        self.finished: dict[str, str] = {}
        self.paused_by: str | None = None
        self.resume_by: str | None = None
        self.cancel_by: str | None = None
        self.approve_by: str | None = None
        self.reruns: list[Rerun] = []
        # 人を待っている作業（同時に回す数に数えない）
        self.waiting: set[str] = set()

    @workflow.signal
    def unit_waiting(self, value: list[Any]) -> None:
        uid, waiting = value
        if waiting:
            self.waiting.add(uid)
        else:
            self.waiting.discard(uid)

    def _busy(self) -> int:
        return len([u for u in self.running if u not in self.waiting])

    @workflow.update
    async def control(self, c: StageControl) -> dict[str, Any]:
        if c.action == "pause":
            self.paused_by = c.by
            await self._to_children(Control("pause", c.by, "boundary"))
        elif c.action == "resume":
            self.paused_by, self.resume_by = None, c.by
            await self._to_children(Control("resume", c.by))
        elif c.action == "cancel":
            self.cancel_by = c.by
            self.pending.clear()
            await self._to_children(Control("cancel_unit", c.by))
        return {"status": self.status}

    @control.validator
    def _check_control(self, c: StageControl) -> None:
        if c.action not in ("pause", "resume", "cancel"):
            raise ValueError(f"知らない操作: {c.action}")
        if self.status in ("done", "cancelled") or self.cancel_by:
            raise ValueError(f"終わった工程（{self.status}）は操作できない")
        if c.action == "pause" and self.paused_by:
            raise ValueError("もう止めている")
        if c.action == "resume" and not self.paused_by and self.status != "blocked":
            raise ValueError("止まっていない")

    @workflow.update
    async def approve(self, by: str) -> dict[str, Any]:
        self.approve_by = by
        return {"approved_by": by}

    @approve.validator
    def _check_approve(self, by: str) -> None:
        if self.status != "awaiting_review":
            raise ValueError(f"工程の検査が終わって判断待ちになってから承認する（今は {self.status}）")

    @workflow.update
    async def rerun(self, r: Rerun) -> dict[str, Any]:
        self.reruns.append(r)
        return {"queued": r.unit_ids}

    @rerun.validator
    def _check_rerun(self, r: Rerun) -> None:
        if not r.unit_ids:
            raise ValueError("作り直す作業を選ぶ")
        if self.cancel_by or self.status in ("done", "cancelled"):
            raise ValueError("終わった工程では作り直せない")
        busy = [u for u in r.unit_ids if u in self.running]
        if busy:
            raise ValueError(f"動いている作業は作り直せない（先に取り消す）: {busy}")

    @workflow.query
    def state(self) -> dict[str, Any]:
        return {"status": self.status, "stage_run_id": self.run_id, "pending": self.pending,
                "running": list(self.running), "finished": self.finished, "paused_by": self.paused_by}

    async def _to_children(self, c: Control) -> None:
        for uid in list(self.running):
            await workflow.get_external_workflow_handle(f"harness-unit-{uid}").signal(WorkUnitWorkflow.parent_control, c)

    async def _rec(self, patch: dict[str, Any], extra: dict[str, Any] | None = None) -> None:
        if "status" in patch:
            self.status = patch["status"]
        await workflow.execute_activity(record_stage, RecordInput(self.run_id, patch, "stage", extra),
                                        start_to_close_timeout=SHORT)

    async def _start_child(self, uid: str) -> None:
        handle = await workflow.start_child_workflow(
            WorkUnitWorkflow.run, UnitInput(uid, self.kind, self.limits["unit"], self.limits["completion"]),
            id=f"harness-unit-{uid}", task_queue=HARNESS_QUEUE, parent_close_policy=ParentClosePolicy.REQUEST_CANCEL)

        async def wait() -> None:
            try:
                res = await handle
                self.finished[uid] = res.get("status", "done")
            except Exception as e:  # 子の失敗（作業の流れの不具合）。工程は止めず、作業を failed として残す
                self.finished[uid] = "failed"
                workflow.logger.warning(f"作業 {uid} の流れが失敗した: {e}")
            finally:
                self.running.pop(uid, None)
                self.waiting.discard(uid)

        self.running[uid] = asyncio.create_task(wait())
        if self.paused_by:
            await handle.signal(WorkUnitWorkflow.parent_control, Control("pause", self.paused_by, "boundary"))

    async def _run_units(self, cap: int) -> None:
        def ready() -> bool:
            return (bool(self.reruns) or (bool(self.pending) and self._busy() < cap and not self.paused_by)
                    or (not self.running and not self.pending))

        while True:
            await workflow.wait_condition(ready)
            if self.reruns:
                r = self.reruns.pop(0)
                self.pending += await workflow.execute_activity(
                    rerun_units, RecordInput(self.run_id, {"unit_ids": r.unit_ids, "by": r.by}),
                    start_to_close_timeout=SHORT)
                continue
            while self.pending and self._busy() < cap and not self.paused_by and not self.cancel_by:
                await self._start_child(self.pending.pop(0))
            if not self.pending and not self.running:
                return

    @workflow.run
    async def run(self, inp: StageInput) -> dict[str, Any]:
        self.run_id, self.limits = inp.stage_run_id, inp.limits
        await self._rec({"status": "running"})
        prepared = await workflow.execute_activity(prepare_stage, self.run_id, start_to_close_timeout=SHORT)
        self.kind, self.pending = prepared["kind"], list(prepared["unit_ids"])
        while True:
            await self._run_units(int(inp.limits["max_parallel_units"]))
            if self.cancel_by:
                await self._rec({"status": "cancelled", "stop_reason": f"{self.cancel_by} が取り消した"})
                return {"status": "cancelled"}
            await self._rec({"status": "running"}, {"phase": "stage_check"})
            try:
                await workflow.execute_activity(
                    stage_check, self.run_id, start_to_close_timeout=CHECK_TIMEOUT,
                    heartbeat_timeout=timedelta(seconds=20),
                    retry_policy=RetryPolicy(maximum_attempts=3,
                                             non_retryable_error_types=["blocked", "refused", "broken_response"]))
            except ActivityError as e:
                cause = e.cause
                msg = cause.message if isinstance(cause, ApplicationError) else str(cause)
                status = "blocked" if isinstance(cause, ApplicationError) and cause.type == "blocked" else "stopped"
                self.resume_by = None
                await self._rec({"status": status, "stop_reason": f"工程の検査: {msg}"})
                # 人が直して resume（検査をやり直す）・作り直し・取り消しのどれかを待つ
                await workflow.wait_condition(lambda: self.resume_by is not None or self.cancel_by is not None
                                              or bool(self.reruns))
                continue
            self.approve_by = None
            await self._rec({"status": "awaiting_review", "stop_reason": None})
            await workflow.wait_condition(lambda: self.approve_by is not None or self.cancel_by is not None
                                          or bool(self.reruns))
            if self.approve_by:
                break
            await self._rec({"status": "running"})
        nxt = await workflow.execute_activity(advance_stage, RecordInput(self.run_id, {"by": self.approve_by}),
                                              start_to_close_timeout=SHORT)
        self.status = "done"
        if nxt is None:
            return {"status": "done", "last": True}
        workflow.continue_as_new(StageInput(nxt, inp.limits))
