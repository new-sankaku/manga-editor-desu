"""Temporal の活動。正本（PostgreSQL）を読み書きするのはここだけ。"""

import asyncio
import time
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from temporalio import activity
from temporalio.exceptions import ApplicationError

from v3server.allowed_destinations import is_allowed
from v3server.canonical_tables.service_and_job_tables import (
    CallLog,
    Job,
    Service,
    ServiceProcess,
)
from v3server.database_engine import get_sessionmaker
from v3server.generation_queue.known_processes import KNOWN_PROCESSES, handle_known_result
from v3server.image_intake import take_in_image
from v3server.llm_questions.answer_json_reader import BrokenAnswerError
from v3server.openfga_permissions import Authz, open_authz
from v3server.operations.image_file_operations import RegisterImage
from v3server.operations.operation_submit_and_undo import submit
from v3server.request_actor import Actor
from v3server.service_senders.sender_by_adapter_name import ADAPTERS
from v3server.service_senders.sender_result_types import AdapterError
from v3server.v3_error_types import V3Error

# ここに載った種類は、活動の中では送り直さない（workflows.py が種類ごとに扱う）
NON_RETRYABLE = ["rate_limited", "refused", "broken_response", "interrupted", "budget", "destination_not_allowed"]

# 活動の生存を Temporal に知らせる間隔（秒）。取り消しは、この知らせの返事で活動に届く
# 1秒：5秒だと「今すぐ止める」が ComfyUI に届くまで最大5秒遅れた（tests/integration/test_harness_perf.py で測った）。
# 作業者の間引き（queue_worker_main の heartbeat_throttle）も1秒なので、これより短くしても速くならない
HEARTBEAT_SECONDS = 1

_authz: Authz | None = None


async def _get_authz() -> Authz:
    global _authz
    if _authz is None:
        async with get_sessionmaker()() as session:
            _authz = await open_authz(session)
    return _authz


async def _heartbeat_forever() -> None:
    while True:
        activity.heartbeat()
        await asyncio.sleep(HEARTBEAT_SECONDS)


def _image_details(job: Job, inputs: list[str]) -> dict:
    """登録する絵の details。画像生成の処理（image_process）なら、処理・引数・シード・候補のまとまり・つなぎ先と、
    元の絵の画素との対応（geometry：新しい画素 = 元の画素 × scale + offset。置き場を引き継ぐときに使う）を書く。"""
    details: dict = {"input_image_ids": inputs} if inputs else {}
    ip = job.request.get("image_process")
    if ip is not None:
        prepared = ip["prepared"]
        details.update(process=ip["name"], params=ip["params"], requested_params=ip.get("requested_params"),
                       seed=ip["seed"], candidate_set_id=ip.get("candidate_set_id"), service_id=job.service_id,
                       geometry=prepared["geometry"] if prepared.get("source_size") else None)
    return details


async def _register_images(session, job: Job, service: Service, images: list[dict]) -> list[dict]:
    """置き場に置いた絵を、AI の操作として登録する（操作の窓口 submit を通す。確定は呼ぶ側が1回で行う）。
    依頼した人の権限で動く。登録の引数は job.request["register"]（comfyui_sender.py の docstring）。"""
    register = job.request["register"]
    actor = Actor(kind="ai", id=f"service:{service.id}", on_behalf_of=job.requested_by)
    authz = await _get_authz()
    registered = []
    inputs = [e["image_id"] for e in job.request.get("prepared_inputs", []) if e.get("image_id")]
    for stored in images:
        op = RegisterImage(
            role=register["role"], origin="generated", page_id=register.get("page_id"),
            panel_id=register.get("panel_id"), job_id=job.id, based_on_image_id=register.get("based_on_image_id"),
            sha256=stored["sha256"], media_type=stored["media_type"], width=stored["width"], height=stored["height"],
            dpi=stored["dpi"], details=_image_details(job, inputs),
        )
        await submit(session, authz, actor, job.work_id, op, commit=False)
        registered.append({"image_id": op.id, "sha256": stored["sha256"]})
    return registered


# 費用を数える呼び出し：送る前の取り置き（sending）・答えを受け取った（received）・登録まで済んだ（ok）・
# 送ったか分からない（unknown）。失敗（failed）と止めた（blocked）は費用を持たない（取り置きを外す）
_COUNTED = ("sending", "received", "ok", "unknown")


async def _month_cost(session, service_id: str) -> Decimal:
    start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = await session.scalar(
        select(func.coalesce(func.sum(CallLog.cost), 0)).where(
            CallLog.service_id == service_id, CallLog.created_at >= start, CallLog.outcome.in_(_COUNTED)
        )
    )
    return Decimal(total)


def _attempt_key(job_id: str) -> str:
    """この依頼のこの回の鍵。同じ依頼でも、ワークフローの回（再開）と活動の呼び出し（待って送り直す）ごとに違う。"""
    info = activity.info()
    return f"{job_id}:{info.workflow_run_id}:{info.activity_id}:{info.attempt}"


@activity.defn
async def call_service(job_id: str) -> None:
    """依頼を1回送り、答えを正本に入れる。作業者が途中で落ちて Temporal がやり直しても、二重に送らず二重に登録しない。

    1. 前の回が答えを受け取って残していれば（received）、送らずにそれを使う（3へ）
    2. 送る前に、鍵と費用の取り置きを持った呼び出しの記録（sending）を確定する。予算はつなぎ先の行を FOR UPDATE で取ってから
       確かめるので、並んだ依頼が同時に上限を超えない。送って失敗したら取り置きを外す（failed）。
       受け取ったら、絵を置き場に置き、答えと入口の判定の記録を1回で確定する（received）
    3. 絵の登録・答えの取り込み・呼び出しの記録（ok）・依頼の終わり（done）を1回で確定する。途中で落ちても何も残らず、
       次の回は 1 から同じ答えで入れ直す
    送った後、答えを残す前に落ちたときは、前の回の記録が sending のまま残る。次の回はそれを unknown（送ったか分からない。
    取り置きは残す）にして、もう一度送る（時間切れ・通信の失敗と同じ扱い。V3細部の決めごと 4.5）。
    """
    attempt = activity.info().attempt
    async with get_sessionmaker()() as session:
        job = await session.get(Job, job_id)
        service = await session.get(Service, job.service_id)
        sp = (
            await session.execute(
                select(ServiceProcess).where(
                    ServiceProcess.service_id == service.id, ServiceProcess.process == job.process
                )
            )
        ).scalar_one_or_none()

        async def stop(kind: str, detail: str, retry_after: float | None = None, call: CallLog | None = None,
                       release: bool = False):
            """記録して止める。call があればその記録に書く（release なら費用の取り置きを外す）。無ければ送らなかった記録を足す。"""
            if call is None:
                session.add(CallLog(job_id=job.id, work_id=job.work_id, service_id=service.id, attempt=attempt,
                                    outcome="blocked" if kind in ("destination_not_allowed", "budget") else "failed",
                                    failure_kind=kind, detail=detail))
            else:
                call.outcome, call.failure_kind, call.detail = "failed", kind, detail
                if release:
                    call.cost = None
            await session.commit()
            raise ApplicationError(detail, {"retry_after": retry_after}, type=kind, non_retryable=kind in NON_RETRYABLE)

        call = (await session.execute(
            select(CallLog).where(CallLog.job_id == job.id, CallLog.outcome == "received")
            .order_by(CallLog.created_at.desc()).limit(1))).scalar_one_or_none()
        if call is None:
            call = await _reserve(session, job, service, sp, attempt, stop)
            await _send_and_keep(session, job, service, sp, call, stop)
        await _finish(session, job_id, service, call, stop)


async def _reserve(session, job: Job, service: Service, sp, attempt: int, stop) -> CallLog:
    """送ってよいかを確かめ、鍵と費用の取り置きを持った記録（sending）を確定する。"""
    for prev in (await session.execute(select(CallLog).where(
            CallLog.job_id == job.id, CallLog.outcome == "sending"))).scalars():
        prev.outcome = "unknown"
        prev.detail = "送った後、答えを残す前に作業者が止まった。送り先で処理されたか・費用がかかったかは分からない"
    # 送る直前にもう一度確かめる。待っている間に送ってよい先から外されたかもしれない
    if not await is_allowed(session, job.work_id, service):
        await stop("destination_not_allowed", f"{service.name} はこの作品の送ってよい先に無い")
    if sp is None:
        await stop("refused", f"{service.name} は {job.process} を受けられない")
    # 予算：つなぎ先の行を取ってから数え、取り置きを足して確定するまで、ほかの依頼はここで待つ
    await session.execute(select(Service.id).where(Service.id == service.id).with_for_update())
    if service.monthly_budget is not None:
        spent = await _month_cost(session, service.id)
        cost = Decimal(sp.cost_per_call) if sp.cost_per_call is not None else Decimal(0)
        if spent >= service.monthly_budget or spent + cost > service.monthly_budget:
            await stop("budget", f"{service.name} の月の予算の上限に達した")
    call = CallLog(job_id=job.id, work_id=job.work_id, service_id=service.id, attempt=attempt, outcome="sending",
                   idempotency_key=_attempt_key(job.id), cost=sp.cost_per_call)
    session.add(call)
    job.status = "running"
    await session.commit()
    return call


async def _send_and_keep(session, job: Job, service: Service, sp, call: CallLog, stop) -> None:
    """送り、受け取った答えを残す（received）。絵は置き場に置き、入口の判定の記録と同じ確定に入れる。"""
    started = time.monotonic()
    # 送っている間も生存を知らせる。人が取り消すと、その返事で CancelledError がここに届き、
    # 送り手（comfyui_sender.py）が送り先の物を止める
    heartbeat = asyncio.create_task(_heartbeat_forever())
    try:
        result = await ADAPTERS[service.adapter](service, sp, job.request)
    except AdapterError as e:
        await stop(e.kind, e.detail, e.retry_after, call=call, release=True)
    except asyncio.CancelledError:
        call.outcome = "unknown"
        call.detail = "送っている間に取り消した。送り先で費用がかかったかは提供元による（未確認）"
        await session.commit()
        raise
    finally:
        heartbeat.cancel()
    call.duration_ms = int((time.monotonic() - started) * 1000)
    call.model, call.settings, call.seed = result.model, result.settings, result.seed
    call.tokens_in, call.tokens_out = result.tokens_in, result.tokens_out
    images = []
    try:
        for data in result.image_files:
            # 生成の出口も、人の絵と同じ入口を通す（規制の判定を差し込む場所。V3ハーネス設計 12章）
            stored = await take_in_image(session, job.work_id, data, "generated", commit=False)
            images.append({"sha256": stored.sha256, "media_type": stored.media_type, "width": stored.width,
                           "height": stored.height, "dpi": stored.dpi})
    except (V3Error, RuntimeError) as e:
        # 答えは受け取ったが使えない（入口で止めた・置き場が無い）。費用はかかっているので取り置きは残す
        await stop("refused", f"絵の登録を断られた: {e}", call=call)
    call.result = {"output": result.output, "images": images}
    call.outcome = "received"
    await session.commit()


async def _finish(session, job_id: str, service: Service, call: CallLog, stop) -> None:
    """受け取った答えを正本に入れ、記録を ok・依頼を done にする。全部を1回で確定する。"""
    job = await session.get(Job, job_id)
    output = dict(call.result["output"])
    try:
        if call.result["images"]:
            # 呼び出しは成功している。絵の登録を断られたら（ロック・権限・置き場）、依頼は止める
            try:
                output["registered"] = await _register_images(session, job, service, call.result["images"])
            except (V3Error, RuntimeError) as e:
                await session.rollback()
                raise ApplicationError(f"絵の登録を断られた: {e}", {"retry_after": None}, type="refused",
                                       non_retryable=True) from e
        if job.process in KNOWN_PROCESSES:
            # 答えを読み、要るものを正本に入れる（依頼した人の代わりのAIとして、操作の窓口を通す）
            actor = Actor(kind="ai", id=f"service:{service.id}", on_behalf_of=job.requested_by)
            try:
                output = await handle_known_result(session, job, actor, await _get_authz(), output, commit=False)
            except BrokenAnswerError as e:
                await session.rollback()
                job = await session.get(Job, job_id)
                job.result = output
                # 崩れた答えは使えないので、次の回で使い直さない（費用はかかっているので取り置きは残す）
                await stop("broken_response", str(e), call=await session.get(CallLog, call.id))
            except V3Error as e:
                await session.rollback()
                raise ApplicationError(f"答えを正本に入れるのを断られた: {e}", {"retry_after": None}, type="refused",
                                       non_retryable=True) from e
    except ApplicationError:
        raise
    except BaseException:
        await session.rollback()
        raise
    job.result = output
    job.status = "done"
    job.failure_kind = job.failure_detail = None
    call.outcome = "ok"
    await session.commit()


@activity.defn
async def set_job_status(job_id: str, status: str, failure_kind: str | None, detail: str | None) -> None:
    async with get_sessionmaker()() as session:
        job = await session.get(Job, job_id)
        job.status = status
        job.failure_kind = failure_kind
        job.failure_detail = detail
        await session.commit()
