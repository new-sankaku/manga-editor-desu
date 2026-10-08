"""P60 の進行役（Temporal のワークフロー）。
- StageWorkflow：1ページの工程 S0〜S7。S4 作画でコマごとに子ワークフローを立て、そろったら S6 でページの検査をする。
- WorkUnitWorkflow：1回の作業（1コマ）。切り出し→文脈を組む→生成（候補k枚）→検査→作り直し→評価→確認待ち。

決まり（AIハーネスのオープンソース実装の調査 5.1 に合わせた）
- 品質の作り直しの回数・予算の使った分はワークフローの変数に持つ。RetryPolicy は通信の失敗の送り直しだけ。
- 人の判断（採用・却下・人の直しの登録・上限の変更）は Update。検証で弾いた操作は履歴に残らない。
- 上流の変更・一時停止・再開・1段の取り消しは Signal。取り消しは協調式で、活動は生存の知らせ（heartbeat）で受け取る。
- 古さは候補ごとの印（使った上流の版と今の版を比べる）。走っている状態の1つにはしない。
- 絵は置き場のファイル名だけを持つ。
"""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError, CancelledError
from temporalio.workflow import ActivityCancellationType

with workflow.unsafe.imports_passed_through():
    import regen_rules

UPSTREAM = "__upstream__"
NODES = ["cut_out", "context", "generate", "check", "evaluate", "review", "done"]
NODE_JA = {"cut_out": "切り出し", "context": "文脈を組む", "generate": "生成", "check": "検査",
           "evaluate": "評価", "review": "確認待ち", "done": "確定"}
STEP_TIMEOUT = {"context": 300, "generate": 900, "check": 300, "evaluate": 600}
HEARTBEAT = timedelta(seconds=15)
NON_RETRY = ["refused", "failed", "interrupted", "broken_response"]


def _iso(t) -> str:
    return t.isoformat()


@workflow.defn
class WorkUnitWorkflow:
    def __init__(self) -> None:
        self.s: dict[str, Any] = {}
        self._handle = None
        self._cancel_reason: str | None = None
        self._paused = False
        self._upstream_pending = False
        self._review_action: dict | None = None
        self._limits_changed = False

    # ------------------------------------------------------------ 状態

    def _ev(self, node: str, kind: str, detail: Any = None) -> None:
        self.s["events"].append({"t": _iso(workflow.now()), "node": node, "kind": kind, "detail": detail,
                                 "attempt": self.s["attempt"]})

    def _node(self, node: str, status: str, detail: Any = None) -> None:
        n = self.s["nodes"][node]
        now = workflow.now()
        if status == "running":
            n["started"] = _iso(now)
            n["count"] += 1
            self.s["current_node"] = node
        elif n.get("started") and n["status"] in ("running", "cancelling"):
            dur = now.timestamp() - _parse(n["started"])
            n["total_s"] = round(n["total_s"] + dur, 2)
            if node in STEP_TIMEOUT:
                self.s["budget"]["seconds"] = round(self.s["budget"]["seconds"] + dur, 2)
        n["status"] = status
        n["detail"] = detail
        self._ev(node, status, detail)

    @workflow.query
    def state(self) -> dict:
        cur = self.s.get("spec_version")
        out = dict(self.s)
        out["candidates"] = [{**c, "stale": c["spec_version"] != cur} for c in self.s.get("candidates", [])]
        out["paused"] = self._paused
        return out

    # ------------------------------------------------------------ 人と上流からの操作

    @workflow.signal
    def pause(self, mode: str = "now") -> None:
        """mode=now：走っている段を取り消して止め、再開でその段からやり直す。boundary：段の切れ目で止まる。"""
        self._paused = True
        self._ev(self.s["current_node"], "pause_requested", mode)
        if mode == "now" and self._handle is not None:
            self._cancel_reason = "pause"
            self._mark_cancelling()
            self._handle.cancel()

    @workflow.signal
    def resume(self) -> None:
        self._paused = False
        self._ev(self.s["current_node"], "resumed")

    @workflow.signal
    def cancel_step(self) -> None:
        if self._handle is not None:
            self._cancel_reason = "step"
            self._mark_cancelling()
            self._handle.cancel()

    @workflow.signal
    def upstream_changed(self, change: dict) -> None:
        """上流（ネーム・設定資料）が変わった。spec の一部を差し替え、版を上げる。
        走っている段は取り消す（その結果は古いので）。作り直しは人が頼む（決めごと 5.4 の既定）。"""
        self.s["spec"] = {**self.s["spec"], **change.get("spec", {})}
        self.s["spec_version"] += 1
        self._upstream_pending = True
        self._ev(self.s["current_node"], "upstream_changed", change)
        if self._handle is not None:
            self._cancel_reason = "upstream"
            self._mark_cancelling()
            self._handle.cancel()

    def _mark_cancelling(self) -> None:
        node = self.s["current_node"]
        self.s["nodes"][node]["status"] = "cancelling"
        self.s["status"] = "cancelling"

    @workflow.update
    def set_limits(self, new: dict) -> dict:
        old = dict(self.s["limits"])
        self.s["limits"].update(new)
        self._limits_changed = True
        self._ev(self.s["current_node"], "limits_changed", {"old": {k: old[k] for k in new}, "new": new})
        return self.s["limits"]

    @set_limits.validator
    def _check_limits(self, new: dict) -> None:
        unknown = set(new) - set(self.s["limits"])
        if unknown:
            raise ValueError(f"知らない上限 {sorted(unknown)}")
        if "max_attempts" in new and new["max_attempts"] < self.s["round_attempts"]:
            raise ValueError(f"回数の上限 {new['max_attempts']} は、もう使った {self.s['round_attempts']} より小さい")
        if "budget_usd" in new and new["budget_usd"] < self.s["budget"]["usd"]:
            raise ValueError(f"費用の上限 {new['budget_usd']} は、もう使った {self.s['budget']['usd']} より小さい")
        if "budget_seconds" in new and new["budget_seconds"] < self.s["budget"]["seconds"]:
            raise ValueError("時間の上限が、もう使った時間より小さい")

    @workflow.update
    def review(self, action: dict) -> str:
        self._review_action = action
        return "受け付けた"

    @review.validator
    def _check_review(self, action: dict) -> None:
        if self.s.get("status") != "awaiting_review":
            raise ValueError(f"判断待ちではない（今は {self.s.get('status')}）")
        kind = action.get("action")
        if kind == "approve":
            best = self._best()
            if best is None:
                raise ValueError("採用できる候補が無い")
            if best["spec_version"] != self.s["spec_version"]:
                raise ValueError("候補が古い（上流が変わった）。却下して作り直すか、上流を戻す")
        elif kind == "reject":
            if not str(action.get("reason", "")).strip():
                raise ValueError("却下には理由が要る")
        elif kind == "edit":
            if not action.get("edited_image") or not action.get("protected_mask"):
                raise ValueError("人の直しには、直した絵と人の手の範囲が要る")
        else:
            raise ValueError(f"知らない操作 {kind}")

    def _best(self) -> dict | None:
        bid = self.s.get("best")
        return next((c for c in self.s["candidates"] if c["id"] == bid), None)

    # ------------------------------------------------------------ 1段の実行

    async def _wait_unpaused(self, node: str) -> None:
        if self._paused:
            self.s["status"] = "paused"
            self.s["nodes"][node]["status"] = "paused"
            self._ev(node, "paused")
            await workflow.wait_condition(lambda: not self._paused)
        self.s["status"] = "running"

    async def _step(self, node: str, act: str, args: dict, pids: list[str] | None = None) -> Any:
        lim = self.s["limits"]
        while True:
            await self._wait_unpaused(node)
            if self._upstream_pending:
                return UPSTREAM
            self._node(node, "running")
            self.s["inflight"] = {"node": node, "pids": pids or [], "since": _iso(workflow.now())}
            self._cancel_reason = None
            self._handle = workflow.start_activity(
                act, args,
                start_to_close_timeout=timedelta(seconds=STEP_TIMEOUT[node]),
                heartbeat_timeout=HEARTBEAT,
                retry_policy=RetryPolicy(initial_interval=timedelta(seconds=2), backoff_coefficient=2,
                                         maximum_attempts=lim["resend_limit"] + 1, non_retryable_error_types=NON_RETRY),
                cancellation_type=ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
            )
            try:
                r = await self._handle
                self._node(node, "done", _summary(node, r))
                if (self.s.get("last_error") or {}).get("node") in (None, node):
                    self.s["errors_in_row"] = 0  # 失敗した段がうまく行ったときだけ数え直す（文脈の段の成功では消さない）
                return r
            except ActivityError as e:
                if isinstance(e.cause, CancelledError):
                    why = self._cancel_reason
                    if why is None:
                        # 段の取り消しを頼んでいないのに取り消された：作業か工程ごとの取り消し
                        self._node(node, "cancelled", "作業ごと取り消した")
                        raise asyncio.CancelledError() from e
                    if why == "pause":
                        self._node(node, "paused", "取り消して止めた。再開でこの段からやり直す")
                        continue
                    if why == "upstream":
                        self._node(node, "stale", "上流が変わったので取り消した")
                        return UPSTREAM
                    self._node(node, "cancelled", "人がこの段を取り消した")
                    return None
                cause = e.cause
                kind = cause.type if isinstance(cause, ApplicationError) else "timeout"
                msg = cause.message if isinstance(cause, ApplicationError) else str(cause)
                self._node(node, "failed", f"{kind}: {msg}")
                self.s["errors_in_row"] += 1
                self.s["last_error"] = {"kind": kind, "message": msg, "node": node}
                return None
            finally:
                self._handle = None
                self.s["inflight"] = None
                if self.s["status"] == "cancelling":
                    self.s["status"] = "running"

    # ------------------------------------------------------------ 止まる理由

    def _limit_reason(self) -> str | None:
        lim, b = self.s["limits"], self.s["budget"]
        if self.s.get("last_error", {}).get("kind") == "refused":
            return "内容で断られた（送り直さない）"
        if self.s["errors_in_row"] >= lim["error_stop"]:
            return f"エラーが{self.s['errors_in_row']}回続いた"
        if self.s["round_attempts"] >= lim["max_attempts"]:
            return f"上限回数（{lim['max_attempts']}回）"
        if b["usd"] >= lim["budget_usd"]:
            return f"予算（費用 {b['usd']:.3f}/{lim['budget_usd']} ドル）"
        if b["seconds"] >= lim["budget_seconds"]:
            return f"予算（時間 {b['seconds']:.0f}/{lim['budget_seconds']} 秒）"
        return None

    # ------------------------------------------------------------ 本体

    @workflow.run
    async def run(self, inp: dict) -> dict:
        self.s = {
            "unit_id": inp["unit_id"], "spec": inp["spec"], "spec_version": 1, "limits": dict(inp["limits"]),
            "mode": inp["mode"], "review_mode": inp["review"], "eval_enabled": inp["eval_enabled"],
            "requester": inp.get("requester", "試作の進行役"), "status": "running", "current_node": "cut_out",
            "nodes": {n: {"status": "queued", "count": 0, "total_s": 0.0, "detail": None} for n in NODES},
            "attempt": 0, "round": 1, "round_attempts": 0, "budget": {"usd": 0.0, "seconds": 0.0},
            "candidates": [], "best": None, "adjust": {"add": [], "neg": []}, "same_failure": 0, "last_sig": None,
            "resets": 0, "errors_in_row": 0, "human_reasons": [], "human": None, "stop_reason": None,
            "review_reason": None, "events": [], "inflight": None, "final": None, "started": _iso(workflow.now()),
            "disagreements": [],
        }
        self._node("cut_out", "running")
        self._node("cut_out", "done", {"対象": inp["spec"]["target_ja"], "完成条件": "検査に全部合格し評価役が"
                                       f"{inp['limits']['eval_min_score']}点以上、人が採用", "上限": inp["limits"],
                                       "依頼した人": self.s["requester"]})
        try:
            need_round = True
            while True:
                if need_round:
                    outcome = await self._work_round(inp)
                else:
                    outcome = self.s["review_reason"]
                if self.s["review_mode"] == "none":
                    return self._finish("stopped" if outcome != "合格" else "done", outcome)
                act = await self._wait_review(outcome)
                kind = act.get("action")
                if kind == "approve":
                    best = self._best()
                    self._node("done", "running")
                    v = await workflow.execute_activity(
                        "register_version", {"unit": self.s["unit_id"], "version": self.s["round"], "image": best["image"]},
                        start_to_close_timeout=timedelta(seconds=60), retry_policy=RetryPolicy(maximum_attempts=3))
                    self._node("done", "done", v)
                    return self._finish("done", "人が採用した", approved=best, version=v)
                if kind == "reject":
                    self.s["human_reasons"].append(act["reason"])
                    self.s["round"] += 1
                    self.s["round_attempts"] = 0
                    self.s["errors_in_row"] = 0
                    self.s.pop("last_error", None)
                    need_round = True
                    continue
                if kind == "edit":
                    await self._human_edit(act)
                    need_round = False
                    continue
                if kind == "limits":
                    need_round = True
                    continue
        except asyncio.CancelledError:
            self.s["status"] = "cancelling"
            self._ev(self.s["current_node"], "unit_cancel_requested")
            pids = [c["pid"] for c in self.s["candidates"] if c["pid"]] + (self.s["inflight"] or {}).get("pids", [])
            for k in range(self.s["limits"]["candidates_per_attempt"]):
                pids.append(self._pid(self.s["attempt"], k))
            res = await workflow.execute_activity(
                "cleanup_unit", {"unit": self.s["unit_id"], "prompt_ids": sorted(set(pids)),
                                 "known_images": [c["image"] for c in self.s["candidates"]]},
                start_to_close_timeout=timedelta(seconds=60))
            self._ev(self.s["current_node"], "cleanup", res)
            self.s["status"] = "cancelled"
            self.s["stop_reason"] = "作業ごと取り消した"
            raise

    def _finish(self, status: str, reason: str, **extra: Any) -> dict:
        self.s["status"] = status
        self.s["stop_reason"] = reason
        self.s["current_node"] = "done"
        self.s["final"] = {"status": status, "reason": reason, **extra}
        self._ev("done", "finished", reason)
        best = self._best()
        return {"unit_id": self.s["unit_id"], "status": status, "reason": reason,
                "image": best["image"] if best else None,
                "persons": best["check"]["persons"] if best and best.get("check") else None,
                "attempts": self.s["attempt"], "budget": self.s["budget"], **extra}

    def _pid(self, attempt: int, cand: int) -> str:
        return _uuid5(
            f"{workflow.info().workflow_id}/{workflow.info().run_id}/r{self.s['round']}/a{attempt}/c{cand}/v{self.s['spec_version']}")

    async def _wait_review(self, reason: str) -> dict:
        self.s["status"] = "awaiting_review"
        self.s["review_reason"] = reason
        self._node("review", "awaiting_review", reason)
        self._review_action = None
        self._limits_changed = False
        notify = self.s["limits"].get("review_notify_seconds")
        stopped_by_limit = self._limit_reason() is not None
        while True:
            try:
                await workflow.wait_condition(
                    lambda: self._review_action is not None
                    or (stopped_by_limit and self._limits_changed and self._limit_reason() is None),
                    timeout=timedelta(seconds=notify) if notify else None)
                break
            except asyncio.TimeoutError:
                self._ev("review", "review_overdue", f"{notify}秒を過ぎた（知らせる）")
                notify = None
        if self._review_action is None:
            self._node("review", "done", "上限が上がったので続ける")
            self.s["status"] = "running"
            return {"action": "limits"}
        act = self._review_action
        self._node("review", "done", act)
        self.s["status"] = "running"
        if act["action"] == "reject" and self._upstream_pending:
            self._upstream_pending = False
        return act

    async def _human_edit(self, act: dict) -> None:
        """人の直しを候補として登録し、検査と評価を掛け直す。人の手の範囲は以後の作り直しで守る。"""
        cand = {"id": f"h{len(self.s['candidates']) + 1}", "pid": None, "image": act["edited_image"], "source": "human",
                "attempt": self.s["attempt"], "cand": 0, "seed": None, "spec_version": self.s["spec_version"],
                "check": None, "eval": None, "round": self.s["round"]}
        self.s["candidates"].append(cand)
        self.s["human"] = {"image": act["edited_image"], "mask": act["protected_mask"]}
        self._ev("review", "human_edit", act)
        await self._check_and_eval([cand])
        self.s["best"] = cand["id"]
        self.s["review_reason"] = "人の直しを検査した"

    async def _check_and_eval(self, cands: list[dict]) -> list[dict]:
        spec, lim = self.s["spec"], self.s["limits"]
        for c in cands:
            r = await self._step("check", "run_checks", {
                "image": c["image"], "expected_persons": spec["expected_persons"], "full_body": spec["full_body"],
                "width": self.s["w"], "height": self.s["h"], "detector_url": self.s.get("detector_url")})
            if r == UPSTREAM:
                return []
            c["check"] = r
        passed = [c for c in cands if c.get("check") and c["check"]["passed"]]
        if not self.s["eval_enabled"]:
            return passed
        for c in passed:
            if self.s["budget"]["usd"] >= lim["budget_usd"]:
                break
            r = await self._step("evaluate", "evaluate", {
                "image": c["image"], "target_ja": spec["target_ja"], "repeats": lim["eval_repeats"],
                "key": f"{self.s['unit_id']}-{c['id']}-v{self.s['spec_version']}", "reasons": self.s["human_reasons"]})
            if r == UPSTREAM:
                return []
            if r is not None:
                c["eval"] = r
                self.s["budget"]["usd"] = round(self.s["budget"]["usd"] + r["cost_usd"], 4)
        return passed

    async def _work_round(self, inp: dict) -> str:
        spec_w, spec_h = inp["width"], inp["height"]
        self.s["w"], self.s["h"] = spec_w, spec_h
        self.s["detector_url"] = inp.get("detector_url")
        while True:
            reason = self._limit_reason()
            if reason:
                self.s["stop_reason"] = reason
                return reason
            if self._upstream_pending:
                self._upstream_pending = False
                self.s["stop_reason"] = "上流が変わった（作り直しは人が頼む）"
                return self.s["stop_reason"]
            lim, spec = self.s["limits"], self.s["spec"]
            self.s["attempt"] += 1
            self.s["round_attempts"] += 1
            a = self.s["attempt"]
            ctx = await self._step("context", "make_context", {
                "spec": spec, "adjustments": self.s["adjust"], "human_reasons": self.s["human_reasons"],
                "cache_key": self.s["unit_id"]})
            if ctx == UPSTREAM:
                continue
            if ctx is None:
                continue
            self.s["budget"]["usd"] = round(self.s["budget"]["usd"] + ctx["cost_usd"], 4)
            self.s["last_context"] = ctx
            new: list[dict] = []
            upstream = False
            for k in range(lim["candidates_per_attempt"]):
                if self._limit_reason() and new:
                    break
                pid = self._pid(a, k)
                seed = inp["base_seed"] + 1000 * (a - 1) + k
                args = {"unit": self.s["unit_id"], "pid": pid, "idempotent": inp["idempotent"], "mode": "t2i",
                        "positive": ctx["positive"], "negative": ctx["negative"], "seed": seed,
                        "width": spec_w, "height": spec_h, "attempt": a, "cand": k,
                        "comfy_url": inp.get("comfy_url"), "unet_override": inp.get("unet_override")}
                if self.s["human"]:
                    args.update(mode="i2i", source=self.s["human"]["image"], protected_mask=self.s["human"]["mask"],
                                strength=0.6)
                r = await self._step("generate", "generate_candidate", args, pids=[pid])
                if r == UPSTREAM:
                    upstream = True
                    break
                if r is None:
                    continue
                c = {"id": f"a{a}c{k}", "pid": r["pid"], "image": r["image"], "source": "ai", "attempt": a, "cand": k,
                     "seed": seed, "spec_version": self.s["spec_version"], "check": None, "eval": None,
                     "round": self.s["round"], "gen_seconds": r["seconds"], "activity_attempt": r["activity_attempt"],
                     "mode": args["mode"]}
                self.s["candidates"].append(c)
                new.append(c)
            if upstream:
                continue
            if not new:
                continue
            passed = await self._check_and_eval(new)
            if self._upstream_pending:
                continue
            failing = [c for c in new if c.get("check") and not c["check"]["passed"]]
            if not passed:
                if failing and self.s["mode"] == "guided":
                    f = failing[0]["check"]
                    sig = regen_rules.failure_signature(f)
                    self.s["same_failure"] = self.s["same_failure"] + 1 if sig == self.s["last_sig"] else 1
                    self.s["last_sig"] = sig
                    adj = regen_rules.adjustments_for(spec, f)
                    if self.s["same_failure"] >= lim["same_failure_reset"]:
                        self.s["adjust"] = adj
                        self.s["resets"] += 1
                        self.s["same_failure"] = 0
                        self._ev("context", "reset_context", sig)
                    else:
                        self.s["adjust"] = regen_rules.merge(self.s["adjust"], adj)
                self._ev("check", "regenerate", [c["check"]["results"] for c in failing])
                continue
            if not self.s["eval_enabled"]:
                self.s["best"] = passed[0]["id"]
                return "合格"
            if any(c.get("eval") is None for c in passed) and not any(
                    c.get("eval") and c["eval"]["median"] >= lim["eval_min_score"] for c in passed):
                self.s["best"] = passed[0]["id"]
                return "判定できない観点がある（評価が終わらなかった）"
            ok = [c for c in passed if c.get("eval") and c["eval"]["median"] >= lim["eval_min_score"]]
            if not ok:
                self.s["disagreements"].append({"attempt": a, "ids": [c["id"] for c in passed],
                                                "scores": [c["eval"]["scores"] for c in passed]})
                self.s["best"] = max(passed, key=lambda c: c["eval"]["median"])["id"]
                self._ev("evaluate", "regenerate", "検査は合格・評価役は不合格")
                continue
            self.s["best"] = max(ok, key=lambda c: c["eval"]["median"])["id"]
            return "合格"


def _parse(iso: str) -> float:
    from datetime import datetime
    return datetime.fromisoformat(iso).timestamp()


def _uuid5(key: str) -> str:
    import uuid
    return str(uuid.uuid5(uuid.UUID("6f6b2c4e-6060-4d0a-9c60-600000000060"), key))


def _summary(node: str, r: Any) -> Any:
    if not isinstance(r, dict):
        return None
    if node == "generate":
        return {"image": r["image"], "seconds": r["seconds"], "activity_attempt": r["activity_attempt"]}
    if node == "check":
        return {"passed": r["passed"], "persons": r["persons"], "touch": r["touch"]}
    if node == "evaluate":
        return {"scores": r["scores"], "median": r["median"], "cost_usd": r["cost_usd"]}
    if node == "context":
        return {"cost_usd": r["cost_usd"], "reason_words": r["reason_words"]}
    return None


# ================================================================ 工程

STAGES = [("S0", "企画"), ("S1", "構成"), ("S2", "設定資料"), ("S3", "ネーム"), ("S4", "作画"),
          ("S5", "仕上げ"), ("S6", "総合"), ("S7", "書き出し")]


@workflow.defn
class StageWorkflow:
    def __init__(self) -> None:
        self.s: dict[str, Any] = {}
        self._children: list[str] = []

    @workflow.query
    def state(self) -> dict:
        return self.s

    def _set(self, sid: str, status: str, detail: Any = None) -> None:
        st = self.s["stages"][sid]
        now = _iso(workflow.now())
        if status == "running":
            st["started"] = now
        else:
            st["ended"] = now
        st["status"] = status
        st["detail"] = detail
        self.s["events"].append({"t": now, "stage": sid, "kind": status, "detail": detail})

    async def _fan_out(self, signal: str, *args: Any) -> None:
        for cid in self._children:
            await workflow.get_external_workflow_handle(cid).signal(signal, *args)

    @workflow.signal
    async def pause(self, mode: str = "now") -> None:
        self.s["paused"] = True
        await self._fan_out("pause", mode)

    @workflow.signal
    async def resume(self) -> None:
        self.s["paused"] = False
        await self._fan_out("resume")

    @workflow.run
    async def run(self, inp: dict) -> dict:
        self.s = {"stage_id": inp["stage_id"], "stages": {k: {"name": n, "status": "queued", "detail": None}
                                                          for k, n in STAGES},
                  "children": [], "events": [], "paused": False, "page": None, "started": _iso(workflow.now())}
        try:
            for sid in ("S0", "S1", "S2"):
                self._set(sid, "done", "試作では固定の入力（harness_config.py）")
            self._set("S3", "running")
            rep = await workflow.execute_activity("name_check", {"panels": inp["panels"]},
                                                  start_to_close_timeout=timedelta(seconds=60))
            self._set("S3", "done" if rep["passed"] else "stopped", rep)
            if not rep["passed"]:
                return {"status": "stopped", "reason": "ネームの検査に不合格"}
            self._set("S4", "running")
            handles = []
            for p in inp["panels"]:
                cid = f"{inp['stage_id']}-p{p['panel']}"
                self._children.append(cid)
                self.s["children"].append(cid)
                unit_inp = {"unit_id": cid, "spec": p, "limits": inp["limits"], "mode": inp["mode"],
                            "review": inp["review"], "eval_enabled": inp["eval_enabled"],
                            "base_seed": inp["base_seed"] + 100 * p["panel"], "idempotent": True,
                            "width": inp["width"], "height": inp["height"], "requester": inp["requester"]}
                handles.append(await workflow.start_child_workflow(WorkUnitWorkflow.run, unit_inp, id=cid))
            results = await asyncio.gather(*handles, return_exceptions=True)
            errs = [r for r in results if isinstance(r, BaseException)]
            if errs:
                self._set("S4", "failed", [str(e) for e in errs])
                return {"status": "failed", "reason": "作画の作業が失敗した"}
            not_done = [r for r in results if r["status"] != "done"]
            self._set("S4", "done" if not not_done else "stopped", [{k: r[k] for k in ("unit_id", "status", "reason")}
                                                                    for r in results])
            if not_done:
                return {"status": "stopped", "reason": "採用されていないコマがある"}
            self._set("S5", "skipped", "試作の対象外（吹き出し・文字は置かない）")
            self._set("S6", "running")
            measured = {str(p["panel"]): r["persons"] for p, r in zip(inp["panels"], results)}
            images = {str(p["panel"]): r["image"] for p, r in zip(inp["panels"], results)}
            page = await workflow.execute_activity(
                "page_check", {"panels": inp["panels"], "measured": measured, "images": images, "stage": inp["stage_id"]},
                start_to_close_timeout=timedelta(seconds=120))
            self.s["page"] = page
            self._set("S6", "done" if page["passed"] else "stopped", page)
            self._set("S7", "done", {"page_image": page["page_image"]})
            return {"status": "done", "page": page}
        except asyncio.CancelledError:
            for sid, st in self.s["stages"].items():
                if st["status"] in ("running", "queued"):
                    self._set(sid, "cancelled", "工程ごと取り消した")
            raise
