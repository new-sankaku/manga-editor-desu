"""つなぎ先と送り先、順番待ちの依頼と呼び出しの記録。"""


from datetime import datetime
from typing import Any

from sqlalchemy import (
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
from sqlalchemy.orm import Mapped, mapped_column

from v3server.canonical_tables.table_base import Base, new_id

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
    # ComfyUI で /history を待つ上限（秒）。既定は置かない。無ければ送らず止める（comfyui_sender.py）
    comfy_wait_seconds: Mapped[int | None] = mapped_column(Integer)
    # 送る前に /object_info で、手順の選択肢（モデル名など）が ComfyUI に入っているか確かめる
    comfy_check_choices: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


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
    # rate_limited / transport / refused / broken_response / interrupted / budget / destination_not_allowed
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
