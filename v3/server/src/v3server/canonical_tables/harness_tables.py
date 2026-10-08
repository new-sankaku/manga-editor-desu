"""AIハーネスの正本（llm_doc/V3ハーネスの実装.md 4章）。

- 工程の実行（HarnessStageRun）：1話の1工程。工程の進行役（親ワークフロー）が1つ持つ
- 作業（HarnessUnit）：作業の決めごと（対象・完成条件・上限・予算・依頼した人・使った上流の版）と、その実行の記録
- 段（HarnessStep）：作業の中の1段（切り出し・文脈・生成・検査・評価・判断待ち・確定）の1回分
- 候補（HarnessCandidate）：生成の1枚。検査の結果・評価・落とした理由を持つ
- 出来事（HarnessEvent）：画面へ送る状態の変化の列（SSE の元。追記のみ）
- 古い印（HarnessStaleMark）：使った上流の版と今の版が違う。結果に付く印で、実行の状態ではない
- 見た出来事の位置（HarnessWatchCursor）：上流の変化を見る所が、作品ごとにどこまで読んだか
- 送信の進み具合（ServiceCallProgress）：ComfyUI の段数と途中の絵。Temporal の履歴には流さない

状態の名前は llm_doc/V3調査/AIハーネスのオープンソース実装の調査.md 6章に合わせる（harness/harness_states.py）。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from v3server.canonical_tables.table_base import Base, JsonType, new_id


class HarnessStageRun(Base):
    __tablename__ = "harness_stage_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), index=True)
    # S0〜S7
    stage: Mapped[str] = mapped_column(String(4))
    status: Mapped[str] = mapped_column(String(24), default="queued")
    requested_by: Mapped[str] = mapped_column(String(128))
    # 作業ごとの上限の初めの値（harness_limits.UnitLimits）と、同時に回す作業の数
    limits: Mapped[dict[str, Any]] = mapped_column()
    # 作業の中身の決めごと（作画なら絵の言葉・処理の引数の土台。harness/unit_spec.py）
    spec: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # 工程の検査の結果（ページの検査・ネームの検査・LLM の問い）
    stage_check: Mapped[dict[str, Any] | None] = mapped_column()
    stop_reason: Mapped[str | None] = mapped_column(Text)
    # この工程を終えて次へ進めた先（次の工程の実行）
    next_stage_run_id: Mapped[str | None] = mapped_column(String(32))
    workflow_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())


class HarnessUnit(Base):
    __tablename__ = "harness_units"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    stage_run_id: Mapped[str] = mapped_column(ForeignKey("harness_stage_runs.id"), index=True)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    stage: Mapped[str] = mapped_column(String(4))
    # panel_drawing（S4 のコマ1つ）・name_draft（S3 の話1つ）
    kind: Mapped[str] = mapped_column(String(24))
    # 対象（panel・episode）
    target_kind: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[str] = mapped_column(String(32))
    page_id: Mapped[str | None] = mapped_column(ForeignKey("pages.id"), index=True)
    # 完成条件（harness_limits.COMPLETION の名前の並び）
    completion: Mapped[list[Any]] = mapped_column()
    limits: Mapped[dict[str, Any]] = mapped_column()
    spec: Mapped[dict[str, Any]] = mapped_column(default=dict)
    requested_by: Mapped[str] = mapped_column(String(128))
    # 切り出したときの上流の版 {上流の鍵: 版}。古いかは今の版と比べて決める
    upstream_used: Mapped[dict[str, Any]] = mapped_column(default=dict)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    current_step: Mapped[str | None] = mapped_column(String(16))
    # 品質の作り直しの回数（1から）。通信の送り直しは数えない
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    cost_used: Mapped[float] = mapped_column(Numeric(12, 4), default=0)
    seconds_used: Mapped[float] = mapped_column(Float, default=0)
    stop_reason: Mapped[str | None] = mapped_column(Text)
    # 人の判断の最後のもの（approve・reject・edit と理由）
    review: Mapped[dict[str, Any] | None] = mapped_column()
    # 確定したもの（採った絵・採ったネームの案）
    result: Mapped[dict[str, Any] | None] = mapped_column()
    # 画面に出す今の待ちの中身（順番待ちの件数・予算で待つなど）
    live: Mapped[dict[str, Any] | None] = mapped_column()
    # 作り直しの前の作業（古くなって作り直したとき・却下のあと人が作り直したとき）
    rerun_of: Mapped[str | None] = mapped_column(String(32))
    workflow_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HarnessStep(Base):
    __tablename__ = "harness_steps"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    unit_id: Mapped[str] = mapped_column(ForeignKey("harness_units.id"), index=True)
    step: Mapped[str] = mapped_column(String(16))
    attempt: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detail: Mapped[dict[str, Any] | None] = mapped_column()
    cost: Mapped[float] = mapped_column(Numeric(12, 4), default=0)


class HarnessCandidate(Base):
    __tablename__ = "harness_candidates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    unit_id: Mapped[str] = mapped_column(ForeignKey("harness_units.id"), index=True)
    attempt: Mapped[int] = mapped_column(Integer)
    k_index: Mapped[int] = mapped_column(Integer)
    # 依頼の重なりを防ぐ鍵（作業・回・何枚目）。落ちて活動が送り直しても同じ依頼を使う
    harness_key: Mapped[str] = mapped_column(String(128), unique=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"))
    image_id: Mapped[str | None] = mapped_column(ForeignKey("image_files.id"))
    # ネームの作業の候補（ネームの案）
    proposal_id: Mapped[str | None] = mapped_column(ForeignKey("name_proposals.id"))
    seed: Mapped[int | None] = mapped_column(BigInteger)
    prompt: Mapped[str | None] = mapped_column(Text)
    # requested / generated / failed / cancelled
    status: Mapped[str] = mapped_column(String(16), default="requested")
    # 検査の結果（検査ごとの合否・判定できない・閾値未設定）
    check: Mapped[dict[str, Any] | None] = mapped_column()
    # pass / flag（仮の閾値で外れた。止めずに指摘だけ）/ drop / unknown
    check_verdict: Mapped[str | None] = mapped_column(String(8))
    evaluation: Mapped[dict[str, Any] | None] = mapped_column()
    picked: Mapped[bool] = mapped_column(Boolean, default=False)
    dropped_reason: Mapped[str | None] = mapped_column(Text)
    # 文の候補（企画・構成・設定資料・総合）の中身
    content: Mapped[dict[str, Any] | None] = mapped_column()
    # 作画の候補の作り方：通った道（下絵・背景・人物の置き方）・使った入力・足りなかった入力・依頼（役目ごと）
    made_with: Mapped[dict[str, Any] | None] = mapped_column()
    # 直させた候補の元（直させる段が作った候補だけ）と、何回目の直しか
    fixed_from: Mapped[str | None] = mapped_column(ForeignKey("harness_candidates.id"))
    fix_round: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HarnessEvent(Base):
    """画面へ送る出来事。id の順に SSE で流す（id が Last-Event-ID）。"""

    __tablename__ = "harness_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    stage_run_id: Mapped[str | None] = mapped_column(String(32), index=True)
    unit_id: Mapped[str | None] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    payload: Mapped[dict[str, Any]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HarnessStaleMark(Base):
    __tablename__ = "harness_stale_marks"
    __table_args__ = (UniqueConstraint("unit_id", "upstream_key", "current_version"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    unit_id: Mapped[str] = mapped_column(ForeignKey("harness_units.id"), index=True)
    upstream_key: Mapped[str] = mapped_column(String(128))
    used_version: Mapped[str | None] = mapped_column(String(64))
    current_version: Mapped[str | None] = mapped_column(String(64))
    # redraw（作画からやり直す）・recheck（検査だけやり直す。設定資料を変えたとき。決めごと 5.4）
    effect: Mapped[str] = mapped_column(String(8))
    reason: Mapped[str] = mapped_column(Text)
    # open / rerun（作り直しを頼んだ）/ dismissed（人がこのままでよいとした）
    status: Mapped[str] = mapped_column(String(12), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HarnessWatchCursor(Base):
    __tablename__ = "harness_watch_cursors"

    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), primary_key=True)
    last_seq: Mapped[int] = mapped_column(BigInteger, default=0)


class ServiceCallProgress(Base):
    """送信の進み具合（comfyui_progress.py が書く）。鍵は依頼の request.progress_key。"""

    __tablename__ = "service_call_progress"

    progress_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    prompt_id: Mapped[str | None] = mapped_column(String(64))
    # pending / running / finished / interrupted / error
    state: Mapped[str] = mapped_column(String(16))
    value: Mapped[int | None] = mapped_column(Integer)
    max: Mapped[int | None] = mapped_column(Integer)
    preview_media_type: Mapped[str | None] = mapped_column(String(32))
    preview_b64: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EpisodeOutline(Base):
    """1話の構成（S1 の正本）。outline = {"pages": [{"page", "summary", "role"}], "highlights": [...], "notes"}。"""

    __tablename__ = "episode_outlines"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), unique=True)
    outline: Mapped[dict[str, Any]] = mapped_column()
    made_by_kind: Mapped[str] = mapped_column(String(8))
    made_by_id: Mapped[str] = mapped_column(String(128))
    human_hand_fields: Mapped[list[Any]] = mapped_column(default=list)
    # 取り消しで「足した」を戻したときの印（行は消さない）
    removed: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class HarnessNotification(Base):
    """知らせ（決めごと 17章）。アプリの中の一覧の1行。外への送り先へは HarnessNotificationDelivery で届ける。"""

    __tablename__ = "harness_notifications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    # info / warn / escalated（判断待ちが長い・締切を過ぎた）
    level: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[dict[str, Any]] = mapped_column()
    stage_run_id: Mapped[str | None] = mapped_column(ForeignKey("harness_stage_runs.id"))
    unit_id: Mapped[str | None] = mapped_column(ForeignKey("harness_units.id"))
    event_id: Mapped[int | None] = mapped_column(BigInteger)
    # 同じ知らせを2回出さない鍵（作業・種類・回など）
    dedupe_key: Mapped[str | None] = mapped_column(String(160), unique=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_by: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HarnessNotificationSetting(Base):
    """作品ごとの知らせの決まり。行が無い作品は、アプリの中の一覧だけに出す（外へは送らない。決めごと 17章）。"""

    __tablename__ = "harness_notification_settings"

    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), primary_key=True)
    kinds: Mapped[list[Any]] = mapped_column()
    # [{"url", "secret"（無ければ署名しない）, "kinds"（無ければ kinds と同じ）}]
    webhooks: Mapped[list[Any]] = mapped_column(default=list)
    escalate_after_notices: Mapped[int | None] = mapped_column(Integer)
    budget_near_ratio: Mapped[float | None] = mapped_column(Float)
    updated_by: Mapped[str] = mapped_column(String(128))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class HarnessNotificationDelivery(Base):
    __tablename__ = "harness_notification_deliveries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    notification_id: Mapped[str] = mapped_column(ForeignKey("harness_notifications.id"), index=True)
    channel: Mapped[str] = mapped_column(String(16))
    target: Mapped[str] = mapped_column(Text)
    # pending / sent / failed（送り直しの上限を超えた）
    status: Mapped[str] = mapped_column(String(16))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    next_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


__all__ = ["HarnessStageRun", "HarnessUnit", "HarnessStep", "HarnessCandidate", "HarnessEvent", "HarnessStaleMark",
           "HarnessWatchCursor", "ServiceCallProgress", "EpisodeOutline", "HarnessNotification",
           "HarnessNotificationSetting", "HarnessNotificationDelivery", "JsonType"]
