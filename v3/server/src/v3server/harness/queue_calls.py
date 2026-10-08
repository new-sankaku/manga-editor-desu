"""ハーネスの活動から、生成・検出器・評価役・LLM を頼む所。どれも今の順番待ち（job_start_and_control.enqueue →
GenerationJob → service_call_activity.call_service）を通す。作品ごとの公平さ・予算・送ってよい先・AIの関与・送り直しが同じにかかる。

- 依頼には harness_key（作業・回・段・何枚目）を入れる。活動が落ちて送り直されても、同じ鍵の依頼があればそれを使う
  （重ねて頼まない）。依頼の行はあるのに流れが始まっていなければ（enqueue の途中で落ちた）、流れだけ始める
- 待つ間は生存を知らせる（heartbeat）。取り消しはこの知らせの返事で届く。届いたら、終わっていない依頼を取り消し、
  止まるまで待ってから取り消しを返す（ComfyUI に送った物は、取り消しを受けた送り手が /queue の delete か
  prompt_id 付きの /interrupt で止める。comfyui_sender.py）
- 待つ間の様子（順番待ち・予算で待つ・制限で待つ）を作業の行と出来事に書く（画面の「送り先を待つ」）
"""

import asyncio
import base64
import contextvars
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from temporalio import activity
from temporalio.client import Client
from temporalio.exceptions import ApplicationError
from temporalio.service import RPCError, RPCStatusCode

from v3server.canonical_tables.harness_tables import HarnessUnit
from v3server.canonical_tables.image_file_tables import ImageFile
from v3server.canonical_tables.service_and_job_tables import CallLog, Job, ProcessRoute
from v3server.database_engine import get_sessionmaker
from v3server.generation_queue import job_start_and_control
from v3server.generation_queue.generation_workflow import JobInput
from v3server.harness.harness_record import patch_unit
from v3server.image_file_storage import read_image
from v3server.openfga_permissions import Authz, open_authz
from v3server.request_actor import Actor
from v3server.v3_error_types import V3Error

# ハーネスが頼む処理の名前。送り先（ProcessRoute）は人が決める。決まっていなければ作業は blocked で止まる
HARNESS_PROCESSES = {
    "panel_tags": "harness_panel_tags",          # LLM：コマの中身からタグの列（作り直しの問い。redo_instruction_question）
    "detect_person": "harness_detect_person",    # 検出器：人物・顔・頭（/person_face_head）
    "detect_text": "harness_detect_text",        # 検出器：絵の中の文字（/text_regions）
    "detect_hands": "harness_detect_hands",      # 検出器：手の枠（/hands。崩れの判定器は無いので人が見る）
    "detect_identity": "harness_detect_identity",  # 検出器：同じ人物か（/identity_ccip。「違う」で落とす専用）
    "detect_age": "harness_detect_age",          # 検出器：年齢区分の確率（/age_rating。記録だけ）
    "shot_angle": "harness_shot_angle",          # VLM：写す範囲・角度・向き（shot_angle_question）
    "pair": "harness_pair",                      # VLM の評価役：2枚を左右を入れ替えて比べる（judge_procedures/pair_comparison）
    "name_draft": "harness_name_draft",          # LLM：ネームの案（name_draft_question）
    "layout_tiers": "harness_layout_tiers",      # LLM：ページの段の割り（layout_tier_question）
    "reading_order": "harness_reading_order",    # VLM：コマの読む順（reading_order_question。ネームの下絵を見せる）
    "contradiction": "harness_contradiction",    # LLM：台本の矛盾（contradiction_question）
    "foreshadow": "harness_foreshadow",          # LLM：伏線の回収漏れ（foreshadow_question）
    "plan_interview": "harness_plan_interview",  # LLM：企画の聞き取り（plan_interview_question）
    "structure": "harness_structure",            # LLM：1話の構成（structure_question）
    "structure_views": "harness_structure_views",  # LLM：構成の観点ごとの指摘（structure_question）
    "imported_text": "harness_imported_text",    # LLM：持ち込んだ文から人物の欄を抜く（imported_text_question）
    "settings_sheet": "harness_settings_sheet",  # LLM：設定資料の案（settings_sheet_question）
    "distinguish": "harness_distinguish",        # LLM：見分けにくい人物の組（settings_sheet_question）
    "page_summary": "harness_page_summary",      # VLM：ページの絵の要約（overall_review_question）
    "outline_compare": "harness_outline_compare",  # LLM：構成と仕上がりの食い違い（overall_review_question）
}

TERMINAL_JOB = frozenset({"done", "stopped", "cancelled"})
POLL_SECONDS = 0.3
CANCEL_WAIT_SECONDS = 60

_temporal: Client | None = None
_authz: Authz | None = None


def configure(temporal: Client) -> None:
    """ハーネスの作業者が起きるときに1回呼ぶ（harness_worker_main.py）。"""
    global _temporal
    _temporal = temporal


def temporal() -> Client:
    if _temporal is None:
        raise RuntimeError("queue_calls.configure が呼ばれていない（ハーネスの作業者の起動の順が違う）")
    return _temporal


async def authz() -> Authz:
    global _authz
    if _authz is None:
        async with get_sessionmaker()() as session:
            _authz = await open_authz(session)
    return _authz


def blocked(detail: str, **details: Any) -> ApplicationError:
    """人が決めるまで進めない（閾値が未設定・送り先が決まっていない・設定資料が足りない）。送り直さない。"""
    return ApplicationError(detail, details, type="blocked", non_retryable=True)


async def require_route(session, key: str) -> str:
    process = HARNESS_PROCESSES.get(key, key)
    if await session.get(ProcessRoute, process) is None:
        raise blocked(f"処理 {process} の送り先が決まっていない（つなぎ先の画面で送り先を決める）", process=process)
    return process


async def ensure_job(session, unit: HarnessUnit, key: str, process: str, request: dict[str, Any],
                     page_id: str | None) -> Job:
    """harness_key の依頼を1件にする。無ければ頼む（AIが工程を進めるための依頼。順番は人の依頼の後）。
    いちばん新しい依頼が取り消し（人が「今すぐ止める」）なら、再開した段は頼み直す。作業者が落ちたときは
    依頼を取り消さない（wait_jobs）ので、ここで頼み直すのは人が止めたときだけ。"""
    existing = (await session.execute(select(Job).where(
        Job.work_id == unit.work_id, Job.request["harness_key"].as_string() == key)
        .order_by(Job.created_at.desc(), Job.id.desc()).limit(1))).scalar_one_or_none()
    if existing is not None and existing.status != "cancelled":
        await _start_if_missing(session, existing)
        return existing
    actor = Actor(kind="ai", id="harness", on_behalf_of=unit.requested_by)
    try:
        return await job_start_and_control.enqueue(session, await authz(), temporal(), actor, unit.work_id, process,
                                                   {**request, "harness_key": key}, "ai", page_id)
    except V3Error as e:
        raise blocked(f"{process} を頼めない: {e}", process=process) from e


async def _start_if_missing(session, job: Job) -> None:
    """依頼の行はあるのに流れが無い（enqueue の途中で落ちた）。流れだけ始める。"""
    try:
        await temporal().get_workflow_handle(job.workflow_id).describe()
        return
    except RPCError as e:
        if e.status != RPCStatusCode.NOT_FOUND:
            raise
    route = await session.get(ProcessRoute, job.process)
    await job_start_and_control._start_and_wait_until_queued(session, temporal(), job, JobInput(
        job.id, job.work_id, job.service_id, job.requested_via, route.resend_limit))


def _wait_state(jobs: list[Job]) -> tuple[str, dict[str, Any]]:
    counts: dict[str, int] = {}
    for j in jobs:
        counts[j.status] = counts.get(j.status, 0) + 1
    for state in ("waiting_budget", "waiting_limit"):
        if counts.get(state):
            return state, counts
    if counts.get("running"):
        return "running", counts
    if counts.get("queued"):
        return "queued", counts
    return "running", counts


@dataclass
class WaitClock:
    """段の中で、送り先の順番を待った秒（依頼がどれも動いていない間）。段の活動（run_step）が1つ置く。"""

    limit: float | None
    waited: float = 0.0


# 今の段の待ちの時計。run_step の外（工程の検査の問い）では None で、待ちを数えない
WAIT_CLOCK: contextvars.ContextVar[WaitClock | None] = contextvars.ContextVar("harness_wait_clock", default=None)


async def wait_jobs(unit_id: str | None, job_ids: list[str]) -> list[Job]:
    """依頼が全部終わるまで待つ。取り消されたら依頼を取り消し、止まるまで待ってから取り消しを返す。
    unit_id が None（工程の検査の問い）なら、待ちの様子は作業の行に書かない。
    依頼がどれも動いていない間は順番待ちとして WAIT_CLOCK に足し、待ちの上限を超えたら依頼を取り消して wait_limit で止める。"""
    last_state = None
    clock = WAIT_CLOCK.get()
    loop = asyncio.get_running_loop()
    seen = loop.time()
    try:
        while True:
            activity.heartbeat({"jobs": job_ids})
            async with get_sessionmaker()() as session:
                jobs = [await session.get(Job, j) for j in job_ids]
                if all(j.status in TERMINAL_JOB for j in jobs):
                    return jobs
                t = loop.time()
                if clock is not None and not any(j.status == "running" for j in jobs):
                    clock.waited += t - seen
                seen = t
                if clock is not None and clock.limit is not None and clock.waited > clock.limit:
                    await asyncio.shield(_cancel_and_wait(job_ids))
                    raise ApplicationError(
                        f"送り先の順番待ちが待ちの上限（{clock.limit:g} 秒）を超えた。上限を上げるか、空いてから再開する",
                        {"waited_seconds": clock.waited}, type="wait_limit", non_retryable=True)
                state, counts = _wait_state(jobs)
                if state != last_state and unit_id is not None:
                    unit = await session.get(HarnessUnit, unit_id)
                    await patch_unit(session, unit_id, {"status": state, "live": {**(unit.live or {}),
                                                                                  "jobs": counts}})
                    await session.commit()
                    last_state = state
            await asyncio.sleep(POLL_SECONDS)
    except asyncio.CancelledError:
        # 作業者が止まる（再起動）ときは依頼を取り消さない。送り直された活動が同じ鍵の依頼を待ち直す
        if not activity.is_worker_shutdown():
            await asyncio.shield(_cancel_and_wait(job_ids))
        raise


async def _cancel_and_wait(job_ids: list[str]) -> None:
    async with get_sessionmaker()() as session:
        for jid in job_ids:
            job = await session.get(Job, jid)
            if job.status in TERMINAL_JOB:
                continue
            try:
                await job_start_and_control.cancel(temporal(), job)
            except RPCError as e:
                if e.status != RPCStatusCode.NOT_FOUND:
                    raise
    deadline = asyncio.get_running_loop().time() + CANCEL_WAIT_SECONDS
    while asyncio.get_running_loop().time() < deadline:
        async with get_sessionmaker()() as session:
            jobs = [await session.get(Job, j) for j in job_ids]
            if all(j.status in TERMINAL_JOB for j in jobs):
                return
        await asyncio.sleep(POLL_SECONDS)


def job_failure(job: Job) -> ApplicationError:
    """止まった依頼を、ハーネスの失敗の種類にする。内容で断られたものは送り直さない（決めごと 4.5）。"""
    kind = job.failure_kind or job.status
    return ApplicationError(f"{job.process} が止まった（{kind}）: {job.failure_detail}", {"job_id": job.id},
                            type="refused" if kind == "refused" else "job_" + kind, non_retryable=True)


async def jobs_cost(session, job_ids: list[str]) -> float:
    if not job_ids:
        return 0.0
    total = await session.scalar(select(func.coalesce(func.sum(CallLog.cost), 0)).where(CallLog.job_id.in_(job_ids)))
    return float(total)


async def ask_text(unit: HarnessUnit, key: str, step: str, messages: list[dict[str, Any]],
                   page_id: str | None = None) -> tuple[str, str]:
    """LLM・VLM に1回聞き、（答えの文, 依頼の id）を返す。"""
    async with get_sessionmaker()() as session:
        process = await require_route(session, step)
        job = await ensure_job(session, unit, key, process, {"messages": messages}, page_id)
        job_id = job.id
    (job,) = await wait_jobs(unit.id, [job_id])
    if job.status != "done":
        raise job_failure(job)
    return job.result["text"], job_id


async def image_data_url(session, image_id: str) -> str:
    img = await session.get(ImageFile, image_id)
    return f"data:{img.media_type};base64," + base64.b64encode(read_image(img.sha256)).decode()


def user_message(question: str, image_urls: list[str]) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "text", "text": question}]
    content += [{"type": "image_url", "image_url": {"url": u}} for u in image_urls]
    return [{"role": "user", "content": content}]
