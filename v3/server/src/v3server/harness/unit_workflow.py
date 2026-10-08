"""作業の流れ（子ワークフロー）。1コマの作画・1話のネームを、切り出し→文脈→生成→検査→評価→判断待ち→確定で回す。

- 品質の作り直しは流れの中で数える（attempt）。通信の失敗の送り直しは活動の RetryPolicy（resend_limit 回）で、数えない
- 止まる理由：上限回数・費用・時間・エラーが続いた・評価が割れた・断られた（harness_limits.stop_reason）。
  止まったら status=stopped で人を待つ。上限を上げる（set_limits）と、止まる理由が消えればそのまま続く
- 人の操作（Update。検証つき）
  - control：pause（now は今の段を取り消して止める。boundary は段の切れ目で止める）・resume・cancel_step（今の段だけ
    取り消して次の回へ）・cancel_unit（作業を取り消す。今の回の候補を却下にしてから cancelled）
  - review：approve（候補か人が直した絵を採る）・reject（理由つき。止まるだけで、人が再開すると作り直す。理由は次の回の
    文脈の問いに入る。上限の redo_on_reject を入れたときだけ、すぐ作り直す。決めごと 5.3）・edit（人が直した絵
    から続ける。人の手の範囲は今の仕組みで貼り戻す）・answer（作業役が人へ返した質問に答える。答えはそれまでの答えと
    一緒に次の回の文脈の問いに入る。却下ではないが、今の回の候補は使わないので却下にする）
  - set_limits：上限を変える（使った分より小さくはできない）
- 工程の進行役からの知らせ（Signal）：parent_control（工程の一時停止・取り消しを伝える）・upstream_changed（上流が
  変わった。作り直しが要る変化なら、段の切れ目で止めて人に聞く。自動で作り直さない）
- 取り消しは活動の取り消しで届け、活動が依頼を取り消して止まり終わるまで待つ（WAIT_CANCELLATION_COMPLETED）。
  半端な候補は discard_round で却下にする（候補の一覧に残さない）
"""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError, CancelledError

with workflow.unsafe.imports_passed_through():
    from v3server.harness.harness_activities import RecordInput, StepInput, record_unit, run_step, unit_usage
    from v3server.harness.harness_limits import check_limit_change, note_failure, stop_reason

RECORD_TIMEOUT = timedelta(seconds=30)
HEARTBEAT_TIMEOUT = timedelta(seconds=20)
NON_RETRYABLE = ["blocked", "refused", "broken_response", "generation_failed", "job_stopped", "job_cancelled",
                 "wait_limit"]
# ワークフローの作りを変えた所の印（workflow.patched）。終わった作業・動いている作業の履歴を読み直す（query・replay）と
# きに、前の作りの履歴は前の道を通る。印は消さない（消してよいのは、印より前に始まった作業が全部消えてから。
# V3ハーネスの実装.md「ワークフローの作りを変えるときの決まり」）
PATCH_CANCEL_AFTER_SUCCESS = "cancel-after-success"  # 取り消しを頼んだ段が成功で終わっても、取り消しを当てる
PATCH_WAIT_NOT_IN_BUDGET = "wait-not-in-budget"      # 送り先の順番待ちを時間の上限に数えず、待ちの上限で持つ
PATCH_REJECT_STOPS = "reject-stops"                  # 却下は止まるだけ（作り直すのは redo_on_reject のときだけ）
CONTROL_ACTIONS = ("pause", "resume", "cancel_step", "cancel_unit")
REVIEW_ACTIONS = ("approve", "reject", "edit", "answer")
HUMAN_WAITS = frozenset({"awaiting_review", "paused", "stopped", "blocked"})


@dataclass
class UnitInput:
    unit_id: str
    kind: str
    limits: dict[str, Any]
    completion: list[str]


@dataclass
class Control:
    action: str
    by: str
    mode: str | None = None  # pause のとき now / boundary


@dataclass
class Review:
    action: str
    by: str
    candidate_id: str | None = None
    image_id: str | None = None
    reason: str | None = None


@dataclass
class LimitChange:
    by: str
    limits: dict[str, Any] = field(default_factory=dict)


class _UnitCancelled(Exception):
    pass


class _StepCancelled(Exception):
    def __init__(self, by: str):
        self.by = by


@workflow.defn
class WorkUnitWorkflow:
    def __init__(self) -> None:
        self.s: dict[str, Any] = {"attempt": 0, "errors_in_row": 0, "disagreements": 0, "refused": None,
                                  "cost_used": 0.0, "seconds_used": 0.0, "last_failure": None, "same_failure": 0,
                                  "failures": []}
        self.unit_id = ""
        self.limits: dict[str, Any] = {}
        self.status = "queued"
        self.step: str | None = None
        self.run_no = 0
        self._cancel_noted = True  # 取り消しを受けた所で「取り消し中」を書き終えたか
        self.current: Any = None
        self.pause_mode: str | None = None
        self.resume_by: str | None = None
        self.cancel_unit_by: str | None = None
        self.cancel_step_by: str | None = None
        self.decision: Review | None = None
        self.upstream: list[dict[str, Any]] = []
        self.upstream_stop = False
        self.limits_changed = False
        self.restart = False

    # ------------------------------------------------------------ 人の操作

    @workflow.update
    async def control(self, c: Control) -> dict[str, Any]:
        self._apply_control(c)
        if c.action == "cancel_unit" and self.status != "cancelling":
            # 段が止まるまで（ComfyUI の取り消しは数秒かかる）待たずに、頼まれた時点で「取り消し中」を出す
            self._cancel_noted = False
            await self._rec({"status": "cancelling"}, "unit", {"by": c.by})
            self._cancel_noted = True
        return {"status": self.status, "step": self.step}

    @control.validator
    def _check_control(self, c: Control) -> None:
        if c.action not in CONTROL_ACTIONS:
            raise ValueError(f"知らない操作: {c.action}")
        if self.status in ("done", "cancelled", "failed"):
            raise ValueError(f"終わった作業（{self.status}）は操作できない")
        if c.action == "pause" and c.mode not in ("now", "boundary"):
            raise ValueError("pause は mode に now か boundary を渡す")
        if c.action == "pause" and self.status in ("paused", "cancelling"):
            raise ValueError(f"今は {self.status}")
        if c.action == "resume" and self.status not in ("paused", "stopped", "blocked") and self.pause_mode is None:
            raise ValueError(f"止まっていない（{self.status}）")
        if c.action == "cancel_step" and (self.current is None or self.step in ("cut_out", "finalize")):
            raise ValueError("取り消せる段が動いていない")
        if c.action == "cancel_unit" and self.cancel_unit_by:
            raise ValueError("もう取り消している")

    @workflow.signal
    def parent_control(self, c: Control) -> None:
        """工程の進行役から。検証は工程の側で済んでいるので、今の状態で意味の無い物だけ捨てる。"""
        try:
            self._check_control(c)
        except ValueError:
            return
        self._apply_control(c)

    def _apply_control(self, c: Control) -> None:
        if c.action == "pause":
            self.pause_mode = c.mode
            if c.mode == "now" and self.current is not None:
                self.current.cancel()
        elif c.action == "resume":
            self.resume_by = c.by
            self.pause_mode = None
        elif c.action == "cancel_step":
            self.cancel_step_by = c.by
            self.current.cancel()
        elif c.action == "cancel_unit":
            self.cancel_unit_by = c.by
            if self.current is not None:
                self.current.cancel()

    @workflow.update
    async def review(self, r: Review) -> dict[str, Any]:
        self.decision = r
        return {"accepted": r.action}

    @review.validator
    def _check_review(self, r: Review) -> None:
        if self.status != "awaiting_review" or self.decision is not None:
            raise ValueError(f"判断待ちでない（{self.status}）")
        if r.action not in REVIEW_ACTIONS:
            raise ValueError(f"知らない判断: {r.action}")
        if r.action == "approve" and (r.candidate_id is None) == (r.image_id is None):
            raise ValueError("採用は candidate_id か image_id のどちらか1つを渡す")
        if r.action == "reject" and not (r.reason or "").strip():
            raise ValueError("却下には理由が要る（次の回の問いに入る）")
        if r.action == "answer" and not (r.reason or "").strip():
            raise ValueError("答え（reason）が要る（次の回の問いに入る）")
        if r.action == "edit" and not r.image_id:
            raise ValueError("人が直した絵（image_id）を渡す")

    @workflow.update
    async def set_limits(self, c: LimitChange) -> dict[str, Any]:
        self.limits = check_limit_change(self.limits, self._used(), c.limits)
        self.limits_changed = True
        await self._rec({"limits": self.limits}, "limits", {"by": c.by})
        return self.limits

    @set_limits.validator
    def _check_limits(self, c: LimitChange) -> None:
        if self.status in ("done", "cancelled", "failed"):
            raise ValueError("終わった作業の上限は変えられない")
        check_limit_change(self.limits, self._used(), c.limits)

    @workflow.signal
    def upstream_changed(self, entries: list[dict[str, Any]]) -> None:
        self.upstream += entries
        if any(e["effect"] == "redraw" for e in entries):
            self.upstream_stop = True

    @workflow.query
    def state(self) -> dict[str, Any]:
        return {"status": self.status, "step": self.step, "s": self.s, "limits": self.limits,
                "pause_mode": self.pause_mode, "upstream": self.upstream}

    def _used(self) -> dict[str, float]:
        return {"attempt": self.s["attempt"], "cost": self.s["cost_used"], "seconds": self.s["seconds_used"]}

    # ------------------------------------------------------------ 記録

    async def _rec(self, patch: dict[str, Any], event: str = "unit", extra: dict[str, Any] | None = None) -> None:
        if "status" in patch:
            was = self.status in HUMAN_WAITS
            self.status = patch["status"]
            now_waiting = self.status in HUMAN_WAITS
            parent = workflow.info().parent
            if parent is not None and was != now_waiting:
                # 人を待つ間は、工程の「同時に回す数」に数えない（AIの手が空いているので次の作業を始めてよい）
                await workflow.get_external_workflow_handle(parent.workflow_id).signal(
                    "unit_waiting", [self.unit_id, now_waiting])
        await workflow.execute_activity(record_unit, RecordInput(self.unit_id, patch, event, extra),
                                        start_to_close_timeout=RECORD_TIMEOUT)

    async def _hold(self, status: str, reason: str, extra: dict[str, Any] | None = None,
                    resume_on_limits: bool = True) -> str:
        """人を待つ（一時停止・止まった・blocked）。resume を受けたら、その人を返す。取り消しなら _UnitCancelled。
        resume_on_limits：止まった理由が上限なら、上限を上げたら再開を待たずに続く（却下で止まったときは続けない）。"""
        self.resume_by = None
        self.limits_changed = False
        await self._rec({"status": status, "stop_reason": reason}, "unit", extra)
        await workflow.wait_condition(lambda: self.resume_by is not None or self.cancel_unit_by is not None
                                      or (status == "stopped" and resume_on_limits and self.limits_changed
                                          and stop_reason(self.limits, self.s) is None
                                          and not self.upstream_stop))
        if self.cancel_unit_by:
            raise _UnitCancelled()
        by = self.resume_by or "set_limits"
        self.resume_by = None
        await self._rec({"status": "running", "stop_reason": None}, "unit", {"resumed_by": by})
        return by

    async def _boundary(self) -> None:
        """段の切れ目。取り消し・一時停止・上流の変化をここで受ける。"""
        if self.cancel_unit_by:
            raise _UnitCancelled()
        if self.pause_mode:
            await self._hold("paused", "人が止めた")
        if self.upstream_stop:
            reasons = "、".join(sorted({e["reason"] for e in self.upstream if e["effect"] == "redraw"}))
            await self._hold("stopped", f"上流が変わった（{reasons}）。続けるか、取り消して作り直すかを人が決める",
                             {"stale": True})
            self.upstream_stop = False
            self.restart = True

    # ------------------------------------------------------------ 段

    async def _step(self, step: str, attempt: int, args: dict[str, Any]) -> dict[str, Any]:
        while True:
            await self._boundary()
            self.run_no += 1
            self.step = step
            wait = self._wait_seconds()
            handle = workflow.start_activity(
                run_step, StepInput(self.unit_id, step, attempt, f"{self.unit_id[:26]}{self.run_no:06d}", args, wait),
                start_to_close_timeout=timedelta(seconds=float(self.limits["budget_seconds"]) + (wait or 0)),
                heartbeat_timeout=HEARTBEAT_TIMEOUT,
                retry_policy=RetryPolicy(maximum_attempts=int(self.limits["resend_limit"]) + 1,
                                         non_retryable_error_types=NON_RETRYABLE),
                cancellation_type=workflow.ActivityCancellationType.WAIT_CANCELLATION_COMPLETED)
            self.current = handle
            try:
                result = await handle
            except ActivityError as e:
                if isinstance(e.cause, CancelledError):
                    if self.cancel_unit_by:
                        raise _UnitCancelled() from e
                    if self.cancel_step_by:
                        by, self.cancel_step_by = self.cancel_step_by, None
                        raise _StepCancelled(by) from e
                    if self.pause_mode == "now":
                        continue  # _boundary で止まり、再開したら同じ段をやり直す
                if isinstance(e.cause, ApplicationError) and e.cause.type == "blocked":
                    await self._hold("blocked", e.cause.message, {"details": list(e.cause.details)})
                    continue
                if isinstance(e.cause, ApplicationError) and e.cause.type == "wait_limit":
                    # 混んでいて待ちの上限を超えた。人が上限を上げるか再開したら、同じ段を頼み直す
                    await self._hold("stopped", e.cause.message, {"wait_limit": True})
                    continue
                raise
            finally:
                self.current = None
                # 段の費用と秒は活動が作業の行に足す（正本は行）。止まる理由の判定のため、行の値を読み直す
                used = await workflow.execute_activity(unit_usage, self.unit_id, start_to_close_timeout=RECORD_TIMEOUT)
                self.s["cost_used"], self.s["seconds_used"] = used["cost_used"], used["seconds_used"]
            # 取り消しを頼んだ段が、取り消しの届く前に成功で終わることがある。temporalio 1.34.0 では、そのとき SDK の
            # 取り消しが消える（p60）。ここでは取り消しを自前の変数で持つので消えないが、段の結果を使わずに頼まれた
            # 取り消しを当てる（当てないと、段の取り消しが黙って捨てられ、作業はそのまま次の段へ進む）
            if workflow.patched(PATCH_CANCEL_AFTER_SUCCESS):
                if self.cancel_unit_by:
                    raise _UnitCancelled()
                if self.cancel_step_by:
                    by, self.cancel_step_by = self.cancel_step_by, None
                    raise _StepCancelled(by)
            return result

    def _wait_seconds(self) -> float | None:
        """段の中で送り先の順番を待ってよい秒（待ちの上限）。待った秒は時間の上限に数えない（p60：数えると、
        混んだときに1台の ComfyUI を待つだけで作業が止まった）。印より前に始まった作業は、上限に wait_seconds が
        無いので前のまま（待ちも時間の上限に入る）。"""
        if workflow.patched(PATCH_WAIT_NOT_IN_BUDGET) and "wait_seconds" in self.limits:
            return float(self.limits["wait_seconds"])
        return None

    async def _discard(self, attempt: int, reason: str, by: str) -> None:
        if attempt < 1:
            return
        await workflow.execute_activity(
            run_step, StepInput(self.unit_id, "discard_round", attempt, "", {"reason": reason, "by": by}),
            start_to_close_timeout=RECORD_TIMEOUT * 4,
            retry_policy=RetryPolicy(maximum_attempts=int(self.limits["resend_limit"]) + 1,
                                     non_retryable_error_types=NON_RETRYABLE))

    async def _await_review(self, attempt: int, picked: str | None) -> Review:
        self.decision = None
        await self._rec({"status": "awaiting_review", "review": {"attempt": attempt, "picked": picked,
                                                                 "since": workflow.now().isoformat()}})
        notices = 0
        while True:
            try:
                await workflow.wait_condition(lambda: self.decision is not None or self.cancel_unit_by is not None,
                                              timeout=timedelta(seconds=float(self.limits["review_notice_seconds"])))
                break
            except TimeoutError:
                notices += 1
                await self._rec({}, "review_notice", {"waited_notices": notices})
        if self.cancel_unit_by:
            raise _UnitCancelled()
        d = self.decision
        self.decision = None
        await self._rec({"status": "running", "review": {"attempt": attempt, "picked": picked, "action": d.action,
                                                         "by": d.by, "reason": d.reason,
                                                         "candidate_id": d.candidate_id, "image_id": d.image_id}},
                        "review", {"action": d.action, "by": d.by, "reason": d.reason})
        return d

    # ------------------------------------------------------------ 本体

    @workflow.run
    async def run(self, inp: UnitInput) -> dict[str, Any]:
        self.unit_id, self.limits = inp.unit_id, dict(inp.limits)
        attempt = 0
        try:
            await self._rec({"status": "running"})
            await self._step("cut_out", 0, {})
            ctx: dict[str, Any] | None = None
            reject_reason: str | None = None
            answers: list[str] = []
            edit_image: str | None = None
            while True:
                reason = stop_reason(self.limits, self.s)
                if reason:
                    await self._hold("stopped", reason)
                    self.s["errors_in_row"], self.s["disagreements"], self.s["refused"] = 0, 0, None
                    continue
                self.s["attempt"] = attempt = self.s["attempt"] + 1
                try:
                    if ctx is None or edit_image is None:
                        ctx = await self._step("context", attempt, {
                            "reject_reason": reject_reason, "previous_tags": (ctx or {}).get("tags"),
                            "restart": self.restart, "answers": answers})
                    self.restart = False
                    seeds = [workflow.random().randint(0, 2**31 - 1)
                             for _ in range(int(self.limits["candidates_per_attempt"]))]
                    await self._step("generate", attempt, {"context": ctx, "seeds": seeds, "edit_image_id": edit_image})
                    skip_size = edit_image is not None
                    chk = await self._step("check", attempt, {"context": ctx, "skip_size": skip_size})
                    edit_image = None
                    self.s["errors_in_row"] = 0
                    # 直させる：落ちた所が直せる所（文字・顔）だけの候補を囲んで直し、直した候補だけ検査し直す
                    rounds = 0
                    while chk.get("fixable") and rounds < int(self.limits["max_fix_rounds"]):
                        rounds += 1
                        await self._step("fix", attempt, {"context": ctx, "round": rounds,
                                                          "candidate_ids": chk["fixable"]})
                        chk = await self._step("check", attempt, {"context": ctx, "skip_size": skip_size})
                    if chk["passed"] == 0:
                        # 全部を作り直すのは、決めて記録してから（黙って作り直さない）
                        why = (f"直す上限（{self.limits['max_fix_rounds']}回）に達しても落ちたまま" if chk.get("fixable")
                               else chk.get("fix_unavailable") or f"直せる所（文字・顔）でない理由で落ちた（{chk['failure']}）")
                        await self._rec({}, "fix_fallback", {"attempt": attempt, "fix_rounds": rounds, "reason": why,
                                                             "decision": "全部を作り直す（文脈から）"})
                        self.restart = note_failure(self.s, chk["failure"], self.limits)
                        continue
                    picked = None
                    if "evaluator_pick" in inp.completion:
                        ev = await self._step("evaluate", attempt, {})
                        if ev["disagree"]:
                            self.s["disagreements"] += 1
                        if ev["picked"] is None:
                            self.restart = note_failure(self.s, ev["failure"], self.limits)
                            continue
                        picked = ev["picked"]
                    if "human_approve" not in inp.completion:
                        await self._rec({"status": "done", "current_step": None,
                                         "result": {"picked": picked, "attempt": attempt, "adopted": False}})
                        return {"status": "done", "picked": picked}
                    d = await self._await_review(attempt, picked)
                    if d.action == "approve":
                        out = await self._step("finalize", attempt, {"by": d.by, "candidate_id": d.candidate_id,
                                                                     "image_id": d.image_id})
                        await self._rec({"status": "done", "current_step": None,
                                         "result": {**out, "attempt": attempt, "approved_by": d.by}})
                        return {"status": "done", **out}
                    if d.action == "reject":
                        reject_reason = d.reason
                        await self._discard(attempt, f"却下: {d.reason}", d.by)
                        # 却下は止まるだけ。作り直すのは人が再開を押したとき（決めごと 5.3）。自動で作り直すのは
                        # 上限の redo_on_reject を入れたときだけ（同 9章の4。既定は入れない）
                        if workflow.patched(PATCH_REJECT_STOPS) and not self.limits.get("redo_on_reject"):
                            await self._hold("stopped", f"却下した（{d.reason}）。作り直すときは再開を押す",
                                             {"rejected_by": d.by}, resume_on_limits=False)
                        continue
                    if d.action == "answer":
                        answers = [*answers, d.reason]
                        await self._discard(attempt, "人が質問に答えた（次の回で答えを入れて作り直す）", d.by)
                        continue
                    edit_image = d.image_id  # 人が直した絵から生成へ戻る（文脈はそのまま）
                except _StepCancelled as c:
                    await self._discard(attempt, "段を取り消した", c.by)
                    await self._rec({"status": "running"}, "step_cancelled", {"by": c.by, "attempt": attempt})
                except ActivityError as e:
                    cause = e.cause
                    kind = cause.type if isinstance(cause, ApplicationError) else type(cause).__name__
                    message = cause.message if isinstance(cause, ApplicationError) else str(cause)
                    if kind == "refused":
                        self.s["refused"] = message
                    self.s["errors_in_row"] += 1
                    self.restart = note_failure(self.s, f"error:{kind}", self.limits) or self.restart
                    await self._rec({}, "error", {"type": kind, "message": message, "attempt": attempt,
                                                  "errors_in_row": self.s["errors_in_row"]})
        except _UnitCancelled:
            by = self.cancel_unit_by
            await workflow.wait_condition(lambda: self._cancel_noted)  # 受けた所の「取り消し中」を先に書き終える
            if self.status != "cancelling":
                await self._rec({"status": "cancelling"}, "unit", {"by": by})
            await self._discard(attempt, "作業を取り消した", by)
            await self._rec({"status": "cancelled", "current_step": None, "stop_reason": f"{by} が取り消した"})
            return {"status": "cancelled"}
