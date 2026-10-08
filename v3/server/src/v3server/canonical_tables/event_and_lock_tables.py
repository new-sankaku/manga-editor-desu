"""出来事の列とロック。"""


from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from v3server.canonical_tables.table_base import Base, new_id

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
