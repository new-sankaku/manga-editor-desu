"""正本と、その周りの表。

作品データ（作品〜コマ）は出来事の列から作った現在の姿。変えるのは操作の窓口（ops/gateway.py）だけ。
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JsonType = JSON().with_variant(JSONB(), "postgresql")


def new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JsonType, list[Any]: JsonType}


# ---------------------------------------------------------------- 作品の階層（作品 ＞ 巻 ＞ 話 ＞ ページ ＞ コマ）


class Work(Base):
    __tablename__ = "works"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(Text)
    # 読む向き（V3細部の決めごと 1章）: rtl=右から / ltr=左から
    reading_direction: Mapped[str] = mapped_column(String(8))
    # 文字の向き（同 2章）: vertical / horizontal
    text_direction: Mapped[str] = mapped_column(String(16))
    # 媒体（同 3章）: paper / web_page / vertical_scroll
    medium: Mapped[str] = mapped_column(String(32))
    trim_size: Mapped[str | None] = mapped_column(String(32))
    default_page_count: Mapped[int | None] = mapped_column(Integer)
    # 出来事の列の最後の番号。書き込みは作品ごとに1本（V3ハーネス設計 9.3）にするため、この行を FOR UPDATE で取る
    head_seq: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Volume(Base):
    __tablename__ = "volumes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(Text)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    volume_id: Mapped[str] = mapped_column(ForeignKey("volumes.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(Text)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed: Mapped[bool] = mapped_column(Boolean, default=False)


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episodes.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    # 抜いたページは消さずに残す（V3細部の決めごと 15章）
    removed: Mapped[bool] = mapped_column(Boolean, default=False)


class Panel(Base):
    __tablename__ = "panels"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id"), index=True)
    # 読む順
    order: Mapped[int] = mapped_column(Integer)
    # 枠（形・大きさ・断ち切り）
    frame: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # 役割（決めゴマ・めくり・ヒキ・つなぎ・場所を見せる）
    role: Mapped[str | None] = mapped_column(String(32))
    # 中身（場所・登場人物・セリフ・擬音など）。形は工程を作るときに決める
    content: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # 人の確定印（V3ハーネス設計 9.2）
    human_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------------------------------------------------------- 出来事の列


class Event(Base):
    """追記のみ。消さない、書き換えない（取り消しも新しい出来事として足す）。"""

    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("work_id", "seq"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    seq: Mapped[int] = mapped_column(BigInteger)
    # human / ai / system
    actor_kind: Mapped[str] = mapped_column(String(8))
    actor_id: Mapped[str] = mapped_column(String(128))
    # AIの作業を頼んだ人。AIはこの人の権限の範囲でしか操作できない
    on_behalf_of: Mapped[str | None] = mapped_column(String(128))
    op_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column()
    # 取り消すときに流す操作。取り消せない出来事（ロックなど）は空
    inverse: Mapped[dict[str, Any] | None] = mapped_column()
    # この出来事が取り消した出来事
    undoes_event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------- ロック


class Lock(Base):
    """ページ・コマ・個別の3段（V3ハーネス設計 4.3）。"""

    __tablename__ = "locks"
    __table_args__ = (UniqueConstraint("target_kind", "target_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    # page / panel / item
    target_kind: Mapped[str] = mapped_column(String(8))
    target_id: Mapped[str] = mapped_column(String(64))
    # 対象が入っているページ。ページのロックとコマ・個別のロックがぶつかるかを見るため
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id"), index=True)
    holder_kind: Mapped[str] = mapped_column(String(8))
    holder_id: Mapped[str] = mapped_column(String(128))
    reason: Mapped[str] = mapped_column(Text)
    # AIのロックなら、その作業。人が取り返したらこの作業を取り消す
    job_id: Mapped[str | None] = mapped_column(String(32))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------- つなぎ先と送り先


class Service(Base):
    """つなぎ先（V3細部の決めごと 4.1・4.7）。手元とAPIを同じ形で持つ。"""

    __tablename__ = "services"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(Text, unique=True)
    # image / text
    kind: Mapped[str] = mapped_column(String(8))
    # local / api。local は手元のPCで、外へ出ない
    location: Mapped[str] = mapped_column(String(8))
    # 呼び方: comfyui / litellm
    adapter: Mapped[str] = mapped_column(String(16))
    # local の住所（ComfyUI）。litellm はサーバーの設定の住所を使う
    endpoint: Mapped[str | None] = mapped_column(Text)
    # serial=1件ずつ / parallel=同時にN件まで（同 4.2）
    send_mode: Mapped[str] = mapped_column(String(8))
    max_concurrency: Mapped[int] = mapped_column(Integer, default=1)
    # connected / stopped / key_rejected / unchecked
    state: Mapped[str] = mapped_column(String(16), default="unchecked")
    # 人が手で止める（休ませる）。止めている間に頼んだものは待ちに入る
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    # 予算: 月の上限（円）。None は上限なし
    monthly_budget: Mapped[float | None] = mapped_column(Numeric(12, 2))


class ServiceProcess(Base):
    """つなぎ先と処理の組ごとの中身・得意さ・費用（同 4.7）。"""

    __tablename__ = "service_processes"
    __table_args__ = (UniqueConstraint("service_id", "process"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), index=True)
    process: Mapped[str] = mapped_column(String(64))
    # ◎=good / ○=normal / △=poor。人が付ける
    aptitude: Mapped[str | None] = mapped_column(String(8))
    cost_per_call: Mapped[float | None] = mapped_column(Numeric(12, 4))
    # API はモデルの名前（LiteLLM の model_name）
    model: Mapped[str | None] = mapped_column(Text)
    # ComfyUI の手順（API形式のJSON）
    comfy_workflow: Mapped[dict[str, Any] | None] = mapped_column()


class ProcessRoute(Base):
    """処理ごとの送り先（同 4.3・4.7）。処理ごとに1つ。"""

    __tablename__ = "process_routes"

    process: Mapped[str] = mapped_column(String(64), primary_key=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"))
    # 送り直しの回数（通信の失敗）と作り直しの回数（出来が悪い）は別に持つ（同 4.5）
    resend_limit: Mapped[int] = mapped_column(Integer, default=3)
    regenerate_limit: Mapped[int] = mapped_column(Integer, default=0)


class WorkDestination(Base):
    """作品の送ってよい先。手元（local）は外へ出ないので常に送ってよい。API はここに載ったものだけ（V3ハーネス設計 17章の6）。"""

    __tablename__ = "work_destinations"

    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), primary_key=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), primary_key=True)


# ---------------------------------------------------------------- 順番待ちと呼び出しの記録


class Job(Base):
    """生成サービスへの1件の依頼。流れは Temporal が持ち、ここは画面に見せる状態と結果を持つ。"""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), index=True)
    process: Mapped[str] = mapped_column(String(64))
    # ページの絵の依頼なら、そのページ（権限はページの can_draw で確かめる）
    page_id: Mapped[str | None] = mapped_column(ForeignKey("pages.id"))
    requested_by: Mapped[str] = mapped_column(String(128))
    # human=人が画面で頼んだ / ai=AIが工程を進めるため（同 4.4: 人を先にする）
    requested_via: Mapped[str] = mapped_column(String(8))
    # queued / running / waiting_limit / waiting_budget / stopped / done / cancelled
    status: Mapped[str] = mapped_column(String(16), default="queued")
    # rate_limited / transport / refused / broken_response / budget / destination_not_allowed
    failure_kind: Mapped[str | None] = mapped_column(String(32))
    failure_detail: Mapped[str | None] = mapped_column(Text)
    request: Mapped[dict[str, Any]] = mapped_column()
    result: Mapped[dict[str, Any] | None] = mapped_column()
    workflow_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CallLog(Base):
    """呼び出し口の記録（V3ハーネス設計 11章）。送った・送らなかったの両方を残す。"""

    __tablename__ = "call_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"))
    attempt: Mapped[int] = mapped_column(Integer)
    model: Mapped[str | None] = mapped_column(Text)
    settings: Mapped[dict[str, Any] | None] = mapped_column()
    seed: Mapped[int | None] = mapped_column(BigInteger)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    cost: Mapped[float | None] = mapped_column(Numeric(12, 4))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    # ok / blocked / failed
    outcome: Mapped[str] = mapped_column(String(8))
    failure_kind: Mapped[str | None] = mapped_column(String(32))
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------- 閾値と、指摘への人の反応


class Threshold(Base):
    """閾値は値・出典・検証の状態を持つデータ（V3ハーネス設計 7章）。作品ごとに持つ。"""

    __tablename__ = "thresholds"
    __table_args__ = (UniqueConstraint("work_id", "key"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    key: Mapped[str] = mapped_column(String(128))
    value: Mapped[dict[str, Any]] = mapped_column()
    source: Mapped[str] = mapped_column(Text)
    # unverified / verified / rejected
    status: Mapped[str] = mapped_column(String(16))
    note: Mapped[str | None] = mapped_column(Text)


class FindingReaction(Base):
    """検査の指摘に人がどう反応したか。閾値の検証の材料（V3ハーネス設計 7章）。"""

    __tablename__ = "finding_reactions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id"), index=True)
    finding_key: Mapped[str] = mapped_column(String(128))
    target_kind: Mapped[str] = mapped_column(String(8))
    target_id: Mapped[str] = mapped_column(String(64))
    # fixed=直した / ignored=見送った / disagreed=指摘が違う
    reaction: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[str] = mapped_column(String(128))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------- サーバーの内部の値


class SystemValue(Base):
    """OpenFGA のストアIDなど、サーバーが自分で作って覚えておく値。"""

    __tablename__ = "system_values"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
